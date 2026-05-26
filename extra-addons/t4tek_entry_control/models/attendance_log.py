from datetime import timezone, datetime, time, timedelta
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

    check_time = fields.Datetime(string="Check Time", required=True, index=True)
    device_check_time = fields.Char(string="Device Check Time")
    device_timezone = fields.Char(string="Device Timezone")

    verify_method = fields.Selection([
        ("fingerprint", "Fingerprint"),
        ("face", "Face"),
        ("card", "Card/RF"),
        ("password", "Password"),
        ("pin", "PIN"),
        ("mixed", "Mixed"),
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
    created_at = fields.Datetime(default=fields.Datetime.now, readonly=True)

    def init(self):
        # Remove heavy/duplicated fields from earlier builds. Odoo does not
        # always drop old columns automatically on upgrade, so do it explicitly.
        self.env.cr.execute("ALTER TABLE IF EXISTS entry_control_attendance_log DROP CONSTRAINT IF EXISTS attendance_event_hash_unique")
        for column in ("event_hash", "pin", "direction_source", "device_direction", "device_check_type"):
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
    def _parse_dt(self, value):
        raw = str(value or "").strip()
        if not raw:
            now = fields.Datetime.now()
            return now, ""
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
            return dt.astimezone(timezone.utc).replace(tzinfo=None), tz
        return dt.replace(tzinfo=None), ""

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
        serial = str(data.get("serial_number") or "").strip()
        api_employee_id = str(data.get("employee_id") or data.get("employeeId") or "").strip()
        legacy_pin = str(data.get("pin") or "").strip()
        check_raw = data.get("check_time") or data.get("checkTime") or data.get("time") or data.get("timestamp")
        check_dt, parsed_tz = self._parse_dt(check_raw)
        device_timezone = data.get("device_timezone") or data.get("deviceTimezone") or parsed_tz or ""
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
            "device_check_time": str(check_raw or ""),
            "device_timezone": device_timezone,
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
    def cron_create_daily_attendances(self, target_date=None):
        """Scheduled action: create/update hr.attendance from raw logs by day.

        Default behavior processes yesterday, so the full day has already ended
        before deriving daily check_in/check_out. Attendance Logs remain the
        audit trail: this method never changes their stored direction.
        """
        if target_date:
            day = fields.Date.to_date(target_date)
        else:
            day = fields.Date.context_today(self) - timedelta(days=1)

        date_from = datetime.combine(day, time.min)
        date_to = datetime.combine(day, time.max)

        logs = self.sudo().search([
            ("check_time", ">=", date_from),
            ("check_time", "<=", date_to),
        ], order="check_time asc, id asc")

        _logger.info(
            "[ENTRY CONTROL] Daily attendance cron started. target_date=%s logs=%s",
            day, len(logs)
        )
        if logs:
            logs.action_sync_hr_attendance()

        params = self.env["ir.config_parameter"].sudo()
        params.set_param("entry_control.last_daily_attendance_cron_at", fields.Datetime.to_string(fields.Datetime.now()))
        params.set_param("entry_control.last_daily_attendance_cron_date", str(day))
        params.set_param("entry_control.last_daily_attendance_cron_log_count", str(len(logs)))
        _logger.info(
            "[ENTRY CONTROL] Daily attendance cron finished. target_date=%s logs=%s",
            day, len(logs)
        )
        return True

    def action_sync_hr_attendance(self):
        # Create/update hr.attendance by day, not by each raw log.
        # Attendance Logs remain the audit trail and their stored direction must
        # NOT be changed by this method. hr.attendance is a derived summary:
        #
        # For each Employee + day:
        # - check_in  = the first Attendance Log whose direction is Check In
        # - check_out = the final raw Attendance Log of the day, if it is after
        #               check_in and there is more than one log in that day
        #
        # This intentionally allows a final raw log that is still marked
        # direction = Check In to be used as the derived daily check_out, without
        # rewriting that Attendance Log. Example:
        #   08:00 Check In, 08:10 Check Out, 13:10 Check In
        # creates hr.attendance 08:00 -> 13:10, while the 13:10 log remains
        # Check In for traceability.
        #
        # API routes are auth=none, so the request env can have no normal
        # singleton user. hr.attendance may access env.user internally during
        # create/write; use an explicit superuser environment to avoid
        # "Expected singleton: res.users()" while still writing the same records.
        super_env = api.Environment(self.env.cr, SUPERUSER_ID, dict(self.env.context or {}))
        Attendance = super_env["hr.attendance"].sudo()
        Log = super_env[self._name].sudo()
        selected_logs = Log.browse(self.ids).sorted(key=lambda r: (r.employee_id.id or 0, r.check_time or datetime.min, r.id))

        grouped = defaultdict(list)
        for rec in selected_logs:
            try:
                if not rec.employee_id:
                    raise ValueError(_("Cannot sync to Attendances: employee not found for this attendance log."))
                if not rec.check_time:
                    raise ValueError(_("Cannot sync to Attendances: check time is empty."))
                day = fields.Date.to_date(rec.check_time)
                grouped[(rec.employee_id.id, day)].append(rec.id)
            except Exception as e:
                rec.write({"sync_status": "failed", "error_message": str(e)})

        for (employee_id, day), log_ids in grouped.items():
            day_logs = Log.browse(log_ids).sorted(key=lambda r: (r.check_time, r.id))
            if not day_logs:
                continue

            check_in_logs = day_logs.filtered(lambda r: r.direction == "in")
            if not check_in_logs:
                day_logs.write({
                    "sync_status": "failed",
                    "error_message": _("Cannot create attendance: no Check In log found for this day."),
                })
                continue

            first_in_log = check_in_logs[0]
            check_in = first_in_log.check_time

            # Derived check_out: use the final raw log of the day. Do not modify
            # that log's direction. If there is only one usable log, keep the
            # hr.attendance open with check_out empty.
            candidate_out_logs = day_logs.filtered(lambda r: r.check_time and r.check_time > check_in)
            last_out_log = candidate_out_logs[-1] if candidate_out_logs else Log.browse()
            check_out = last_out_log.check_time if last_out_log else False

            try:
                if check_out and check_out < check_in:
                    raise ValueError(_("Cannot create attendance: check out is before check in."))

                day_start = datetime.combine(day, time.min)
                day_end = datetime.combine(day, time.max)
                attendance = Attendance.search([
                    ("employee_id", "=", employee_id),
                    ("check_in", ">=", day_start),
                    ("check_in", "<=", day_end),
                ], order="check_in asc, id asc", limit=1)
                if not attendance:
                    attendance = Attendance.search([
                        ("employee_id", "=", employee_id),
                        ("check_out", ">=", day_start),
                        ("check_out", "<=", day_end),
                    ], order="check_in asc, id asc", limit=1)

                vals = {"employee_id": employee_id, "check_in": check_in}
                if check_out:
                    vals["check_out"] = check_out
                elif attendance and attendance.check_out:
                    vals["check_out"] = False

                if attendance:
                    attendance.write(vals)
                else:
                    attendance = Attendance.create(vals)

                day_logs.write({
                    "hr_attendance_id": attendance.id,
                    "sync_status": "success",
                    "error_message": False,
                })
            except Exception as e:
                day_logs.write({"sync_status": "failed", "error_message": str(e)})
        return True
