from datetime import timezone, datetime, time, timedelta
from zoneinfo import ZoneInfo
from collections import defaultdict
import logging
from dateutil import parser as date_parser
from odoo import api, fields, models, _, SUPERUSER_ID



_logger = logging.getLogger(__name__)


class EntryControlAttendanceLog(models.Model):
    _name = "entry.control.attendance.log"
    _description = "Entry Control Attendance Log"
    _order = "check_time desc, id desc"

    controller_id = fields.Many2one("entry.control.controller", ondelete="set null", index=True)
    device_id = fields.Many2one("entry.control.device", string="Device Record", ondelete="set null", index=True)
    serial_number = fields.Char(string="Device", index=True, readonly=True)
    employee_id = fields.Many2one("hr.employee", ondelete="set null", index=True)

    # Final operational direction used to create/update hr.attendance.
    direction = fields.Selection([("in", "Check In"), ("out", "Check Out")], default="in", required=True, index=True)

    # Stored exactly as the Controller/device local punch time.
    # If the controller sends `2026-05-27 07:47:06+07`, the value stored here
    # is `2026-05-27 07:47:06` so Attendance Logs show the same clock time.
    check_time = fields.Datetime(string="Check Time", required=True, index=True)

    verify_method = fields.Selection([
        ("fingerprint", "Fingerprint"),
        ("face", "Face"),
        ("card", "Card/RF"),
        ("password", "Password"),
        ("pin", "PIN"),
        ("mixed", "Mixed"),
        ("system_generated", "System Generated"),
        ("unknown", "Unknown"),
    ], default="unknown", index=True)
    verify_type = fields.Char(string="Verify Type")
    check_type = fields.Char(string="Check Type")

    hr_attendance_id = fields.Many2one("hr.attendance", string="HR Attendance", ondelete="set null", readonly=True, index=True)
    sync_status = fields.Selection([
        ("success", "Success"),
        ("failed", "Failed"),
        ("skipped", "Skipped"),
    ], default="success", index=True)
    error_message = fields.Text()
    message = fields.Text(string="Message", readonly=True)
    created_at = fields.Datetime(default=fields.Datetime.now, readonly=True)

    def init(self):
        # Remove heavy/duplicated fields from earlier builds. Odoo does not
        # always drop old columns automatically on upgrade, so do it explicitly.
        self.env.cr.execute("ALTER TABLE IF EXISTS entry_control_attendance_log DROP CONSTRAINT IF EXISTS attendance_event_hash_unique")
        for column in ("event_hash", "pin", "direction_source", "device_direction", "device_check_type", "is_system_generated", "check_time_local", "device_check_time", "device_timezone"):
            self.env.cr.execute('ALTER TABLE IF EXISTS entry_control_attendance_log DROP COLUMN IF EXISTS "%s"' % column)
        # Backfill the canonical serial_number field on upgrades. Older builds
        # used a device_serial_number column; copy it first, then fall back to
        # the linked device record.
        self.env.cr.execute("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                     WHERE table_name = 'entry_control_attendance_log'
                       AND column_name = 'device_serial_number'
                ) THEN
                    UPDATE entry_control_attendance_log
                       SET serial_number = device_serial_number
                     WHERE (serial_number IS NULL OR serial_number = '')
                       AND device_serial_number IS NOT NULL
                       AND device_serial_number <> '';
                END IF;
            END $$;
        """)
        self.env.cr.execute("""
            UPDATE entry_control_attendance_log l
               SET serial_number = d.serial_number
              FROM entry_control_device d
             WHERE l.device_id = d.id
               AND (l.serial_number IS NULL OR l.serial_number = '')
        """)
        self.env.cr.execute('ALTER TABLE IF EXISTS entry_control_attendance_log DROP COLUMN IF EXISTS "device_serial_number"')

    @api.model
    def _employee_code_fields(self):
        Employee = self.env["hr.employee"]
        # The SEM module already provides hr.employee.code (Mã nhân viên).
        # Keep fallback names only for tolerant upgrades/custom HR modules.
        preferred = ["code", "employee_code", "identification_id"]
        return [fname for fname in preferred if fname in Employee._fields]

    @api.model
    def _employee_pin_fields(self):
        Employee = self.env["hr.employee"]
        # SEM/Odoo HR already provides pin; entry_control_pin is only a legacy fallback.
        preferred = ["pin", "entry_control_pin"]
        return [fname for fname in preferred if fname in Employee._fields]

    @api.model
    def _employee_pin(self, employee):
        for field_name in self._employee_pin_fields():
            value = str(employee[field_name] or "").strip()
            if value:
                return value
        return ""

    @api.model
    def find_employee_by_employee_id(self, employee_id):
        # Current API meaning: employee_id is Employee Code / Mã nhân viên,
        # not the numeric Odoo database ID. Numeric ID fallback is kept only for
        # tolerant upgrades from older Controller builds.
        raw = str(employee_id or "").strip()
        Employee = self.env["hr.employee"].sudo()
        if not raw:
            return Employee.browse()
        for field_name in self._employee_code_fields():
            emp = Employee.search([(field_name, "=", raw)], limit=1)
            if emp:
                return emp
        try:
            return Employee.browse(int(raw)).exists()
        except Exception:
            return Employee.browse()

    @api.model
    def find_employee_by_pin(self, pin):
        # Legacy fallback only. New API matching should use employee_id =
        # Employee Code / Mã nhân viên.
        pin = str(pin or "").strip()
        if not pin:
            return self.env["hr.employee"].browse()
        Employee = self.env["hr.employee"].sudo()
        for field_name in self._employee_code_fields() + self._employee_pin_fields():
            emp = Employee.search([(field_name, "=", pin)], limit=1)
            if emp:
                return emp
        return Employee.browse()

    @api.model
    def _attendance_timezone_name(self):
        """Business timezone used for device/local attendance days.

        Odoo stores Datetime values as naive UTC. Device logs and synthetic
        23:59 / 00:00 rows are business-local times, so always convert them
        through this timezone instead of depending on the cron/user timezone.
        """
        try:
            value = self.env["ir.config_parameter"].sudo().get_param("entry_control.attendance_timezone")
        except Exception:
            value = False
        return value or "Asia/Ho_Chi_Minh"

    @api.model
    def _attendance_timezone(self):
        try:
            return ZoneInfo(self._attendance_timezone_name())
        except Exception:
            return ZoneInfo("Asia/Ho_Chi_Minh")

    @api.model
    def _local_naive_to_utc(self, value):
        """Compatibility helper name kept for old calls.

        Attendance Logs now store device/controller clock time exactly as sent,
        not converted to UTC. Synthetic 23:59 / 00:00 rows therefore also use
        the same local naive value.
        """
        dt = fields.Datetime.to_datetime(value)
        if not dt:
            return False
        return dt.replace(tzinfo=None)

    @api.model
    def _utc_naive_to_local(self, value):
        """Compatibility helper name kept for old calls.

        Values in entry.control.attendance.log.check_time are already device
        local naive datetimes. Return them unchanged.
        """
        dt = fields.Datetime.to_datetime(value)
        return dt.replace(tzinfo=None) if dt else False

    @api.model
    def _business_day_from_utc(self, value):
        dt = fields.Datetime.to_datetime(value)
        return dt.date() if dt else False

    @api.model
    def _business_day_bounds_utc(self, day):
        day = fields.Date.to_date(day)
        return datetime.combine(day, time.min), datetime.combine(day, time.max)

    @api.model
    def _business_now_date(self):
        return datetime.now(self._attendance_timezone()).date()

    @api.model
    def _parse_dt(self, value):
        """Parse Controller check_time and preserve the device clock time.

        Example: `2026-05-27 07:47:06+07` is stored as
        `2026-05-27 07:47:06`, not converted to `00:47:06` UTC. This module
        intentionally treats Attendance Logs as device-local operational data.
        """
        raw = str(value or "").strip()
        if not raw:
            return fields.Datetime.now(), ""
        text = raw.replace("Z", "+00:00")
        try:
            dt = date_parser.isoparse(text) if ("T" in text or "+" in text[-6:] or "-" in text[-6:]) else fields.Datetime.to_datetime(text)
        except Exception:
            dt = date_parser.parse(text)
        tz = ""
        if getattr(dt, "tzinfo", None):
            tz = dt.strftime("%z") or str(dt.tzinfo)
            if len(tz) == 5:
                tz = "%s:%s" % (tz[:3], tz[3:])
        return dt.replace(tzinfo=None), tz or self._attendance_timezone_name()

    @api.model
    def _device_direction_from_check_type(self, check_type):
        text = str(check_type or "").strip().lower().replace("-", "_").replace(" ", "_")
        if text in ("1", "2", "5", "out", "check_out", "checkout", "break_out", "ot_out", "clock_out", "exit"):
            return "out"
        return "in"

    @api.model
    def _infer_direction(self, employee, check_dt, device_direction=None):
        # Server-owned operational direction. Do not trust direction / AttState
        # codes sent by the device or Controller.
        # Rule: if the previous Attendance Log of the employee is Check In,
        # the next log is Check Out; otherwise it is Check In.
        if not employee:
            return "in"
        previous_log = self.sudo().search([
            ("employee_id", "=", employee.id),
            ("check_time", "<", check_dt),
            ("direction", "in", ["in", "out"]),
        ], order="check_time desc, id desc", limit=1)
        if previous_log and previous_log.direction == "in":
            return "out"
        return "in"

    def action_recompute_directions(self):
        # Recompute directions for a selected batch in chronological order.
        # This is used before Create Attendances so historical logs imported
        # out of order still follow the same server-owned alternating rule.
        Log = self.sudo()
        logs = Log.browse(self.ids).filtered(lambda r: r.employee_id and r.check_time)
        employees = logs.mapped("employee_id")
        for employee in employees:
            emp_logs = logs.filtered(lambda r: r.employee_id.id == employee.id).sorted(key=lambda r: (r.check_time, r.id))
            if not emp_logs:
                continue
            first_dt = emp_logs[0].check_time
            previous_log = Log.search([
                ("employee_id", "=", employee.id),
                ("check_time", "<", first_dt),
                ("direction", "in", ["in", "out"]),
            ], order="check_time desc, id desc", limit=1)
            next_direction = "out" if previous_log and previous_log.direction == "in" else "in"
            for log in emp_logs:
                if log.direction != next_direction:
                    log.write({"direction": next_direction})
                next_direction = "out" if next_direction == "in" else "in"
        return True

    @api.model
    def _verify_method_from_type(self, verify_type):
        text = str(verify_type or "").strip().lower().replace("-", "_").replace(" ", "_")
        if not text:
            return "unknown"
        if any(x in text for x in ("finger", "fp", "vân", "van_tay")):
            return "fingerprint"
        if "face" in text:
            return "face"
        if any(x in text for x in ("card", "rf")):
            return "card"
        if any(x in text for x in ("pin", "password", "pwd")):
            return "pin" if "pin" in text else "password"
        try:
            code = int(float(text))
        except Exception:
            return "unknown"
        if code == 0:
            return "password"
        if code == 1:
            return "fingerprint"
        if code in (2, 4):
            return "card"
        if code in (3,):
            return "password"
        if code in (15, 16):
            return "face"
        return "mixed"

    @api.model
    def _find_existing_log(self, controller, device, serial_number, employee, check_time, check_type, verify_type):
        # Deduplicate by Serial Number, not by IP/device name. Device rows can be
        # reassigned between Controllers, while the physical serial remains stable.
        domain = [
            ("controller_id", "=", controller.id if controller else False),
            ("serial_number", "=", serial_number or ""),
            ("employee_id", "=", employee.id if employee else False),
            ("check_time", "=", check_time),
            ("check_type", "=", check_type or ""),
            ("verify_type", "=", verify_type or ""),
        ]
        existing = self.sudo().search(domain, limit=1)
        if existing:
            return existing
        # Upgrade fallback for logs created before serial_number existed.
        legacy_domain = [
            ("controller_id", "=", controller.id if controller else False),
            ("device_id", "=", device.id if device else False),
            ("employee_id", "=", employee.id if employee else False),
            ("check_time", "=", check_time),
            ("check_type", "=", check_type or ""),
            ("verify_type", "=", verify_type or ""),
        ]
        return self.sudo().search(legacy_domain, limit=1)

    @api.model
    def ingest_direct_log(self, controller, data):
        data = dict(data or {})
        # API contract is strict: attendance payload must identify the device by
        # the physical ZKTeco Serial Number in ``serial_number`` only.
        serial = str(
            data.get("serial_number")
            or data.get("serialNumber")
            or data.get("device_serial_number")
            or data.get("deviceSerialNumber")
            or ""
        ).strip()
        api_employee_id = str(data.get("employee_id") or data.get("employeeId") or "").strip()
        legacy_pin = str(data.get("pin") or "").strip()
        check_raw = data.get("check_time") or data.get("checkTime") or data.get("time") or data.get("timestamp")
        check_dt, parsed_tz = self._parse_dt(check_raw)
        check_type = str(data.get("check_type") or data.get("checkType") or "").strip()
        verify_type = str(data.get("verify_type") or data.get("verifyType") or "").strip()

        Device = self.env["entry.control.device"].sudo()
        device = Device.browse()
        if serial:
            device = Device.search([("serial_number", "=", serial)], limit=1)
            if not device:
                # Create a placeholder from the attendance payload so the log is
                # still linked by Serial Number even if /devices/report has not
                # run yet. IP address remains informational only.
                device = Device.upsert_from_payload(controller, {
                    "serial_number": serial,
                    "name": serial,
                    "ip_address": data.get("ip_address") or data.get("ipAddress"),
                    "status": "online",
                })
        employee = self.find_employee_by_employee_id(api_employee_id)
        if not employee and legacy_pin:
            employee = self.find_employee_by_pin(legacy_pin)

        existing = self._find_existing_log(controller, device, serial, employee, check_dt, check_type, verify_type)
        if existing:
            return existing, True

        # Direction is decided by the server only. Device check_type / AttState
        # is stored as raw information, not used as the operational direction.
        direction = self._infer_direction(employee, check_dt)
        verify_method = data.get("verify_method") or data.get("verifyMethod") or self._verify_method_from_type(verify_type)
        vals = {
            "controller_id": controller.id,
            "device_id": device.id if device else False,
            "serial_number": serial,
            "employee_id": employee.id if employee else False,
            "direction": direction,
            "check_time": check_dt,
            "verify_method": verify_method if verify_method in dict(self._fields["verify_method"].selection) else "unknown",
            "verify_type": verify_type,
            "check_type": check_type,
            "sync_status": "success",
        }
        rec = self.sudo().create(vals)
        # Keep raw Attendance Logs only when API receives logs.
        # hr.attendance records are created manually from the list-view
        # Create Attendances wizard.
        return rec, False



    @api.model
    def _make_system_log_message(self, direction, local_dt, reason):
        # Keep the user-facing note short. Technical details are already
        # represented by verify_method/check_type = system_generated.
        return _("Hệ thống tự tạo")

    @api.model
    def _find_or_create_system_log(self, source_log, direction, local_dt, reason):
        """Create a synthetic Attendance Log at a business-local datetime.

        Attendance Logs are the only source used to calculate hr.attendance.
        Therefore missing boundary events must be represented as log rows, not
        silently inferred while writing hr.attendance.
        """
        check_time = self._local_naive_to_utc(local_dt)
        domain = [
            ("employee_id", "=", source_log.employee_id.id),
            ("check_time", "=", check_time),
            ("direction", "=", direction),
            ("verify_method", "=", "system_generated"),
        ]
        existing = self.sudo().search(domain, limit=1)
        if existing:
            return existing
        message = self._make_system_log_message(direction, local_dt, reason)
        vals = {
            "controller_id": source_log.controller_id.id if source_log.controller_id else False,
            "device_id": source_log.device_id.id if source_log.device_id else False,
            "serial_number": source_log.serial_number or (source_log.device_id.serial_number if source_log.device_id else ""),
            "employee_id": source_log.employee_id.id,
            "direction": direction,
            "check_time": check_time,
            "verify_method": "system_generated",
            "verify_type": "system",
            "check_type": "system_generated",
            "sync_status": "success",
            "message": message,
        }
        return self.sudo().create(vals)

    @api.model
    def _resequence_employee_logs(self, employee, start_dt=None, end_dt=None):
        """Keep operational direction continuous for an employee.

        Raw device state remains available in check_type/verify_type. The
        direction field is the server-owned operational direction used by
        Attendance calculation, so it must be Check In -> Check Out -> Check In
        continuously after synthetic 23:59 / 00:00 rows are inserted.
        """
        if not employee:
            return self.browse()
        domain = [("employee_id", "=", employee.id), ("check_time", "!=", False)]
        if start_dt:
            domain.append(("check_time", ">=", start_dt))
        if end_dt:
            domain.append(("check_time", "<=", end_dt))
        logs = self.sudo().search(domain, order="check_time asc, id asc")
        if not logs:
            return logs
        previous = self.sudo().search([
            ("employee_id", "=", employee.id),
            ("check_time", "<", logs[0].check_time),
            ("direction", "in", ["in", "out"]),
        ], order="check_time desc, id desc", limit=1)
        next_direction = "out" if previous and previous.direction == "in" else "in"
        for log in logs:
            if log.direction != next_direction:
                log.write({"direction": next_direction})
            next_direction = "out" if next_direction == "in" else "in"
        return logs

    @api.model
    def _ensure_continuous_logs_for_days(self, logs):
        """Insert missing 23:59 Check Out and 00:00 next-day Check In logs.

        This method intentionally creates rows in Attendance Logs first. The
        hr.attendance summary is then calculated only from Attendance Logs.
        """
        Log = self.sudo()
        logs = Log.browse(logs.ids).filtered(lambda r: r.employee_id and r.check_time)
        if not logs:
            return logs
        employees = logs.mapped("employee_id")
        original_min_day = min(Log._business_day_from_utc(l.check_time) for l in logs)
        original_max_day = max(Log._business_day_from_utc(l.check_time) for l in logs)
        # Include the previous business day so a carry-over 00:00 created from
        # yesterday can be rebuilt instead of becoming stale. Include one extra
        # day after the selected range because 00:00 next-day is generated there.
        min_local_day = original_min_day - timedelta(days=1)
        max_local_day = original_max_day
        search_from, _search_from_end = Log._business_day_bounds_utc(min_local_day)
        _search_to_start, search_to = Log._business_day_bounds_utc(max_local_day + timedelta(days=1))
        affected = Log.browse()
        for employee in employees:
            # Rebuild system-generated boundary logs in this window. This removes
            # stale 23:59/00:00 rows if a real Check Out later arrives.
            stale_system_logs = Log.search([
                ("employee_id", "=", employee.id),
                ("check_type", "=", "system_generated"),
                ("verify_method", "=", "system_generated"),
                ("check_time", ">=", search_from),
                ("check_time", "<=", search_to),
            ])
            if stale_system_logs:
                stale_system_logs.unlink()

            # First normalize existing real directions in the requested window.
            emp_logs = Log._resequence_employee_logs(employee, search_from, search_to)
            affected |= emp_logs
            # Re-query per day after resequencing and insert missing boundaries.
            day = min_local_day
            while day <= max_local_day:
                day_start, day_end = Log._business_day_bounds_utc(day)
                day_logs = Log.search([
                    ("employee_id", "=", employee.id),
                    ("check_time", ">=", day_start),
                    ("check_time", "<=", day_end),
                ], order="check_time asc, id asc")
                if day_logs:
                    last_log = day_logs[-1]
                    if last_log.direction == "in":
                        checkout_local = datetime.combine(day, time(23, 59, 0))
                        next_checkin_local = datetime.combine(day + timedelta(days=1), time(0, 0, 0))
                        affected |= Log._find_or_create_system_log(
                            last_log,
                            "out",
                            checkout_local,
                            _("missing Check Out at the end of the day"),
                        )
                        # Only keep the 00:00 next-day placeholder when the
                        # next business day has no real Attendance Logs yet.
                        # If the employee already punched on the next day, that
                        # real Check In must be used for hr.attendance instead
                        # of a system-generated 00:00 row.
                        next_day_start, next_day_end = Log._business_day_bounds_utc(day + timedelta(days=1))
                        next_day_real_logs = Log.search([
                            ("employee_id", "=", employee.id),
                            ("check_time", ">=", next_day_start),
                            ("check_time", "<=", next_day_end),
                            ("verify_method", "!=", "system_generated"),
                        ], limit=1)
                        if not next_day_real_logs:
                            affected |= Log._find_or_create_system_log(
                                last_log,
                                "in",
                                next_checkin_local,
                                _("carry-over Check In for the next day after a system-generated 23:59 Check Out"),
                            )
                day += timedelta(days=1)
            # Resequence again after inserting synthetic rows, including the
            # next day 00:00 row and any existing real logs that follow it.
            affected |= Log._resequence_employee_logs(employee, search_from, search_to)
            affected |= Log.search([
                ("employee_id", "=", employee.id),
                ("check_time", ">=", search_from),
                ("check_time", "<=", search_to),
            ], order="check_time asc, id asc")
        return affected

    @api.model
    def cron_create_daily_attendances(self, target_date=None):
        """Scheduled action: create/update hr.attendance from Attendance Logs.

        Demo behavior: the cron runs every minute and processes the current
        business day immediately. It never creates hr.attendance directly from
        guessed times; it first makes Attendance Logs continuous, then derives
        Attendances from those logs.
        """
        if target_date:
            day_from = fields.Date.to_date(target_date)
            day_to = day_from
        else:
            # Demo-safe behavior: process yesterday and today every minute.
            # Yesterday covers missed overnight runs; today gives immediate
            # feedback for customer demos.
            day_to = self._business_now_date()
            day_from = day_to - timedelta(days=1)

        date_from, _unused_start_end = self._business_day_bounds_utc(day_from)
        _unused_to_start, date_to = self._business_day_bounds_utc(day_to)
        logs = self.sudo().search([
            ("check_time", ">=", date_from),
            ("check_time", "<=", date_to),
        ], order="check_time asc, id asc")

        _logger.info(
            "[ENTRY CONTROL] Daily attendance cron started. target_range=%s..%s tz=%s logs=%s",
            day_from, day_to, self._attendance_timezone_name(), len(logs)
        )
        if logs:
            logs.with_context(
                entry_control_target_day_from=str(day_from),
                entry_control_target_day_to=str(day_to),
            ).action_sync_hr_attendance()

        params = self.env["ir.config_parameter"].sudo()
        params.set_param("entry_control.attendance_timezone", self._attendance_timezone_name())
        params.set_param("entry_control.last_daily_attendance_cron_at", fields.Datetime.to_string(fields.Datetime.now()))
        params.set_param("entry_control.last_daily_attendance_cron_date", "%s..%s" % (day_from, day_to))
        params.set_param("entry_control.last_daily_attendance_cron_log_count", str(len(logs)))
        params.set_param("entry_control.last_daily_attendance_cron_timezone", self._attendance_timezone_name())
        _logger.info(
            "[ENTRY CONTROL] Daily attendance cron finished. target_range=%s..%s logs=%s",
            day_from, day_to, len(logs)
        )
        return True

    @api.model
    def _entry_control_attendance_messages(self):
        """Messages used to identify hr.attendance rows managed by this module."""
        return [
            "Hệ thống tự tạo",
            "Tính từ Attendance Logs",
        ]

    @api.model
    def _managed_attendances_for_day(self, Attendance, day_logs, employee_id, day_start, day_end):
        """Return hr.attendance rows that are clearly managed by Entry Control.

        Never blindly update an arbitrary/manual Odoo attendance row just
        because it is on the same day. This prevents Create Attendances/Cron
        from overwriting a user's manual attendance.
        """
        managed = Attendance.browse()
        linked = day_logs.mapped("hr_attendance_id").exists()
        if linked:
            managed |= linked
        if "message" in Attendance._fields:
            managed |= Attendance.search([
                ("employee_id", "=", employee_id),
                ("message", "in", self._entry_control_attendance_messages()),
                "|",
                    "&", ("check_in", ">=", day_start), ("check_in", "<=", day_end),
                    "&", ("check_out", ">=", day_start), ("check_out", "<=", day_end),
            ])
        return managed

    @api.model
    def _cleanup_entry_control_open_attendances(self, Attendance, employee_ids, start_dt, end_dt):
        """Remove stale open hr.attendance rows previously created by Entry Control.

        Attendance Logs are the source of truth. The synthetic 00:00 Check In
        row is allowed to exist in Attendance Logs, but it must not leave an
        open hr.attendance row that blocks the next day's real attendance.
        We only clean records that are clearly managed by this module, using
        the message field added by Entry Control.
        """
        employee_ids = [eid for eid in set(employee_ids or []) if eid]
        if not employee_ids or "message" not in Attendance._fields:
            return Attendance.browse()
        domain = [
            ("employee_id", "in", employee_ids),
            ("check_out", "=", False),
            ("check_in", ">=", start_dt),
            ("check_in", "<=", end_dt),
            ("message", "in", self._entry_control_attendance_messages()),
        ]
        stale = Attendance.search(domain)
        if stale:
            _logger.info(
                "[ENTRY CONTROL] Removing %s stale open Entry Control attendance row(s) before recalculation.",
                len(stale),
            )
            stale.unlink()
        return stale

    def action_sync_hr_attendance(self):
        # Attendance calculation rule:
        # 1) Attendance Logs are the source of truth.
        # 2) If a business day ends with Check In, create system Attendance Logs:
        #      - Check Out at 23:59 of the same day
        #      - Check In at 00:00 of the next day
        # 3) Then create/update one CLOSED hr.attendance per Employee + business day:
        #      - check_in  = first Check In log of that business day
        #      - check_out = last Check Out log of that business day
        # 4) Never create an open hr.attendance. A system 00:00 Check In may
        #    remain in Attendance Logs, but it must not become an open
        #    hr.attendance that blocks later records.
        super_env = api.Environment(self.env.cr, SUPERUSER_ID, dict(self.env.context or {}))
        Attendance = super_env["hr.attendance"].sudo()
        Log = super_env[self._name].sudo()
        selected_logs = Log.browse(self.ids).filtered(lambda r: r.employee_id and r.check_time)
        if not selected_logs:
            return True

        # Capture target days before _ensure_continuous_logs_for_days() because
        # that method may delete/rebuild stale system-generated 00:00/23:59 rows.
        target_days = set(Log._business_day_from_utc(l.check_time) for l in selected_logs if l.check_time)
        ctx_day_from = self.env.context.get("entry_control_target_day_from")
        ctx_day_to = self.env.context.get("entry_control_target_day_to")
        if ctx_day_from and ctx_day_to:
            day_from = fields.Date.to_date(ctx_day_from)
            day_to = fields.Date.to_date(ctx_day_to)
            target_days = {d for d in target_days if d and day_from <= d <= day_to}

        all_logs = Log._ensure_continuous_logs_for_days(selected_logs)
        all_logs = all_logs.filtered(lambda r: r.employee_id and r.check_time)
        if not all_logs:
            return True

        employee_ids = all_logs.mapped("employee_id").ids
        min_day = min(Log._business_day_from_utc(l.check_time) for l in all_logs if l.check_time)
        max_day = max(Log._business_day_from_utc(l.check_time) for l in all_logs if l.check_time)
        cleanup_from, _cleanup_from_end = Log._business_day_bounds_utc(min_day)
        _cleanup_to_start, cleanup_to = Log._business_day_bounds_utc(max_day)
        Log._cleanup_entry_control_open_attendances(Attendance, employee_ids, cleanup_from, cleanup_to)

        # Only create/update hr.attendance for the requested business days.
        # _ensure_continuous_logs_for_days() intentionally looks one day before
        # and one day after the selected logs to maintain boundary rows, but the
        # summary Attendances must not leak outside the wizard/cron target range.
        selected_days = target_days
        grouped = defaultdict(list)
        for rec in all_logs:
            day = Log._business_day_from_utc(rec.check_time)
            if day in selected_days:
                grouped[(rec.employee_id.id, day)].append(rec.id)

        for (employee_id, day), log_ids in grouped.items():
            day_logs = Log.browse(log_ids).sorted(key=lambda r: (r.check_time, r.id))
            if not day_logs:
                continue

            check_in_logs = day_logs.filtered(lambda r: r.direction == "in")
            if not check_in_logs:
                fail_message = _("Cannot create attendance: no Check In log found for this day.")
                day_logs.write({
                    "sync_status": "failed",
                    "error_message": fail_message,
                    "message": fail_message,
                })
                continue
            check_out_logs = day_logs.filtered(lambda r: r.direction == "out")
            first_in_log = check_in_logs[0]
            last_out_log = check_out_logs[-1] if check_out_logs else Log.browse()
            check_in = first_in_log.check_time
            check_out = last_out_log.check_time if last_out_log else False

            day_start, day_end = Log._business_day_bounds_utc(day)
            generated_logs = day_logs.filtered(lambda r: r.verify_method == "system_generated")
            message = _("Hệ thống tự tạo") if generated_logs else _("Tính từ Attendance Logs")

            try:
                # Do not create an open attendance. The 00:00 system Check In is
                # stored only in Attendance Logs until a corresponding Check Out
                # exists for the same business day.
                if not check_out:
                    # Remove stale open rows generated by older module versions.
                    # Prefer precise matching by check_in so we do not touch a
                    # legitimate manual Odoo attendance opened at another time.
                    managed_for_day = Log._managed_attendances_for_day(Attendance, day_logs, employee_id, day_start, day_end)
                    stale_open = managed_for_day.filtered(lambda a: not a.check_out)
                    if stale_open:
                        stale_open.unlink()
                    day_logs.write({
                        "hr_attendance_id": False,
                        "sync_status": "skipped",
                        "error_message": False,
                    })
                    # Keep the short note only on system-generated Attendance Logs.
                    generated_logs.write({"message": _("Hệ thống tự tạo")})
                    real_logs = day_logs - generated_logs
                    if real_logs:
                        real_logs.write({"message": False})
                    continue

                if check_out < check_in:
                    raise ValueError(_("Cannot create attendance: check out is before check in."))

                managed_for_day = Log._managed_attendances_for_day(Attendance, day_logs, employee_id, day_start, day_end)
                attendance = managed_for_day.sorted(key=lambda a: (a.check_in or datetime.min, a.id))[:1]
                duplicate_attendances = managed_for_day - attendance
                if duplicate_attendances:
                    duplicate_attendances.unlink()

                vals = {
                    "employee_id": employee_id,
                    "check_in": check_in,
                    "check_out": check_out,
                }
                if "message" in Attendance._fields:
                    vals["message"] = message

                if attendance:
                    attendance.write(vals)
                else:
                    attendance = Attendance.create(vals)

                day_logs.write({
                    "hr_attendance_id": attendance.id,
                    "sync_status": "success",
                    "error_message": False,
                })
                generated_logs.write({"message": _("Hệ thống tự tạo")})
                real_logs = day_logs - generated_logs
                if real_logs:
                    real_logs.write({"message": False})
            except Exception as e:
                fail_message = str(e)
                day_logs.write({
                    "sync_status": "failed",
                    "error_message": fail_message,
                    "message": fail_message,
                })
        return True
