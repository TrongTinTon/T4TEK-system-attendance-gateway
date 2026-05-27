from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from collections import defaultdict
import logging
import re
from dateutil import parser as date_parser
from odoo import api, fields, models, _, SUPERUSER_ID



_logger = logging.getLogger(__name__)


class EntryControlAttendanceLog(models.Model):
    _name = "entry.control.attendance.log"
    _description = "Entry Control Attendance Log"
    _order = "check_time desc, id desc"

    _DEFAULT_ATTENDANCE_TIMEZONE = "Asia/Ho_Chi_Minh"
    _CONFIG_ATTENDANCE_TIMEZONE = "entry_control.attendance_timezone"
    _SYSTEM_GENERATED_TIMEZONE_MARKER = "0"

    controller_id = fields.Many2one("entry.control.controller", ondelete="set null", index=True)
    device_id = fields.Many2one("entry.control.device", string="Device Record", ondelete="set null", index=True)
    serial_number = fields.Char(string="Device", index=True, readonly=True)
    device_timezone = fields.Char(string="Device Timezone", readonly=True, index=True)
    employee_id = fields.Many2one("hr.employee", ondelete="set null", index=True)

    # Final operational direction used to create/update hr.attendance.
    direction = fields.Selection([("in", "Check In"), ("out", "Check Out")], default="in", required=True, index=True)

    # Single persisted Check Time column for Attendance Logs.
    # It follows Odoo's normal Datetime rule: stored as UTC-naive in DB.
    # Example controller value `2026-05-27 09:45:23+07` is stored as
    # `2026-05-27 02:45:23` in check_time, while device_timezone keeps the
    # device offset note for real logs. System-generated logs keep
    # device_timezone = 0 and use the module timezone configuration for
    # local-day / boundary calculation.
    check_time = fields.Datetime(string="Check Time", required=True, index=True)

    # UI-only module-local time. Keep it as Char so Odoo does not apply the
    # current user's timezone a second time.
    # Formula: convert canonical Check Time (UTC-naive) to Module Timezone.
    # This is intentionally based on entry_control.attendance_timezone for both
    # real device logs and system-generated logs. device_timezone remains an
    # audit/context note only and is not added again.
    time_display = fields.Char(string="Time", compute="_compute_time_display", readonly=True)

    # UI-only diagnostic field: shows the current server-side time calculated
    # with the Entry Control module timezone configuration. This helps verify
    # whether entry_control.attendance_timezone is really running as expected,
    # independently from the browser/computer timezone and the current Odoo
    # user's timezone. Keep it as Char so Odoo does not convert it again.
    module_time_now = fields.Char(string="Module Time Now", compute="_compute_module_time_runtime", readonly=True)
    module_timezone_display = fields.Char(string="Module Timezone", compute="_compute_module_time_runtime", readonly=True)

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
        for column in (
            "event_hash",
            "pin",
            "direction_source",
            "device_direction",
            "device_check_type",
            "is_system_generated",
            "check_time_local",
            "device_check_time",
            "check_time_stored_display",
            "check_time_display",
            "check_time_db_utc",
            "check_time_device_local",
        ):
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

        # Keep the module timezone deterministic after upgrades. Older builds or
        # tests may have left entry_control.attendance_timezone as UTC, which
        # makes the Time column show UTC instead of Vietnam local time. Do this
        # with SQL UPSERT so upgrades never hit duplicate ir.config_parameter
        # errors. Only empty/UTC-like values are corrected; valid custom
        # non-UTC timezones are preserved.
        self.env.cr.execute(
            """
            INSERT INTO ir_config_parameter
                (key, value, create_uid, create_date, write_uid, write_date)
            VALUES
                (%s, %s, 1, NOW(), 1, NOW())
            ON CONFLICT (key) DO UPDATE
               SET value = EXCLUDED.value,
                   write_uid = 1,
                   write_date = NOW()
             WHERE ir_config_parameter.value IS NULL
                OR ir_config_parameter.value = ''
                OR ir_config_parameter.value IN ('UTC', 'Etc/UTC', 'GMT', 'GMT0')
            """,
            (self._CONFIG_ATTENDANCE_TIMEZONE, self._DEFAULT_ATTENDANCE_TIMEZONE),
        )

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
    def _extract_timezone_note_from_text(self, value):
        """Return timezone suffix from a controller timestamp as context.

        Example: ``2026-05-27 09:12:05+07`` returns ``+07:00``. The suffix is
        stored in device_timezone and is used later to group UTC-stored logs by
        Device Local Time.
        """
        raw = str(value or "").strip()
        if not raw:
            return False
        if raw.endswith("Z") or raw.endswith("z"):
            return "+00:00"
        match = re.search(r"([+-]\d{2})(?::?(\d{2}))?$", raw)
        if match:
            return "%s:%s" % (match.group(1), match.group(2) or "00")
        return False

    @api.model
    def _strip_timezone_note_from_text(self, value):
        """Remove only the final timezone suffix from controller Check Time."""
        raw = str(value or "").strip()
        if not raw:
            return raw
        if raw.endswith("Z") or raw.endswith("z"):
            return raw[:-1].strip()
        return re.sub(r"([+-]\d{2})(?::?\d{2})?$", "", raw).strip()

    @api.model
    def _normalize_check_time_value(self, value, device_timezone=None):
        """Normalize Check Time into Odoo UTC-naive storage.

        Controller/device sends a local wall-clock time plus an offset, for example
        ``2026-05-27 09:45:23+07``. The value stored in Odoo must be UTC-naive:
        ``2026-05-27 02:45:23``. If the input has no explicit offset, use the
        supplied device_timezone, then the module attendance timezone fallback.
        """
        if not value:
            return value
        if isinstance(value, str):
            raw = value.strip().replace("T", " ")
            try:
                parsed = date_parser.parse(raw)
            except Exception:
                parsed = fields.Datetime.to_datetime(raw)
            if not parsed:
                return value
            if parsed.tzinfo:
                return parsed.astimezone(timezone.utc).replace(tzinfo=None)
            tzinfo = self._tzinfo_from_device_timezone(device_timezone or self._extract_timezone_note_from_text(value))
            return parsed.replace(tzinfo=tzinfo).astimezone(timezone.utc).replace(tzinfo=None)
        dt = fields.Datetime.to_datetime(value)
        if not dt:
            return value
        if dt.tzinfo:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        tzinfo = self._tzinfo_from_device_timezone(device_timezone)
        return dt.replace(tzinfo=tzinfo).astimezone(timezone.utc).replace(tzinfo=None)

    @api.model
    def _normalize_utc_storage_value(self, value):
        """Return a UTC-naive datetime without applying device_timezone again.

        Use this when caller already converted a Device Local time to UTC before
        invoking create/write.
        """
        if not value:
            return value
        if isinstance(value, str):
            try:
                dt = date_parser.parse(value.replace("T", " "))
            except Exception:
                dt = fields.Datetime.to_datetime(value)
        else:
            dt = fields.Datetime.to_datetime(value)
        if not dt:
            return value
        if dt.tzinfo:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt.replace(tzinfo=None)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("check_time"):
                if not vals.get("device_timezone"):
                    tz_note = self._extract_timezone_note_from_text(vals.get("check_time"))
                    if tz_note:
                        vals["device_timezone"] = tz_note
                vals["device_timezone"] = self._normalize_device_timezone(vals.get("device_timezone"))
                if self.env.context.get("entry_control_check_time_is_utc"):
                    vals["check_time"] = self._normalize_utc_storage_value(vals.get("check_time"))
                else:
                    vals["check_time"] = self._normalize_check_time_value(vals.get("check_time"), vals.get("device_timezone"))
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals or {})
        if vals.get("check_time"):
            if not vals.get("device_timezone"):
                tz_note = self._extract_timezone_note_from_text(vals.get("check_time"))
                if tz_note:
                    vals["device_timezone"] = tz_note
            vals["device_timezone"] = self._normalize_device_timezone(vals.get("device_timezone"))
            if self.env.context.get("entry_control_check_time_is_utc"):
                vals["check_time"] = self._normalize_utc_storage_value(vals.get("check_time"))
            else:
                vals["check_time"] = self._normalize_check_time_value(vals.get("check_time"), vals.get("device_timezone"))
        return super().write(vals)

    @api.model
    def _timezone_offset_delta(self, tz_value=None, base_dt=None):
        """Return UTC offset for a timezone/offset value at a reference time."""
        tz = self._normalize_device_timezone(tz_value)
        if tz == self._SYSTEM_GENERATED_TIMEZONE_MARKER:
            tz = self._attendance_timezone_name()
        if not tz:
            tz = self._attendance_timezone_name()
        if tz and tz[0:1] in ("+", "-"):
            sign = 1 if tz[0] == "+" else -1
            body = tz[1:]
            try:
                if ":" in body:
                    hh, mm = body.split(":", 1)
                else:
                    hh, mm = body[:2], body[2:] or "0"
                return sign * timedelta(hours=int(hh), minutes=int(mm))
            except Exception:
                return timedelta(0)
        try:
            tzinfo = ZoneInfo(tz)
            ref = fields.Datetime.to_datetime(base_dt) or datetime.utcnow()
            if not ref.tzinfo:
                ref = ref.replace(tzinfo=timezone.utc)
            return tzinfo.utcoffset(ref) or timedelta(0)
        except Exception:
            return timedelta(0)

    @api.model
    def _device_timezone_matches_module(self, device_timezone=None, base_dt=None):
        """Check whether the device offset matches the module timezone offset.

        Example: ``+07:00`` matches ``Asia/Ho_Chi_Minh`` at the same reference
        timestamp. This check is diagnostic only; parsing still trusts the
        explicit offset carried by the controller timestamp.
        """
        if not device_timezone:
            return True
        device_tz = self._normalize_device_timezone(device_timezone)
        if device_tz == self._SYSTEM_GENERATED_TIMEZONE_MARKER:
            return True
        return self._timezone_offset_delta(device_tz, base_dt) == self._timezone_offset_delta(self._attendance_timezone_name(), base_dt)

    @api.model
    def _format_check_time_in_module_timezone(self, value):
        """Format canonical UTC-naive check_time in the module timezone.

        This is the only display rule for the Time column:
            Time = check_time (UTC storage) -> entry_control.attendance_timezone

        It does not use the Odoo user's timezone and it does not add
        device_timezone again. A controller timestamp such as
        2026-05-27 13:18:00+07 is stored as 2026-05-27 06:18:00 UTC-naive and
        is displayed here as 2026-05-27 13:18:00 when the module timezone is
        Asia/Ho_Chi_Minh.
        """
        dt = fields.Datetime.to_datetime(value)
        if not dt:
            return False
        # Odoo Datetime storage is UTC-naive. Treat any naive datetime as UTC.
        dt_utc = dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        local_dt = dt_utc.astimezone(self._attendance_timezone()).replace(tzinfo=None)
        return local_dt.strftime("%Y-%m-%d %H:%M:%S")

    def _is_system_generated_log(self):
        self.ensure_one()
        return (
            self.verify_method == "system_generated"
            or self.check_type == "system_generated"
            or self.device_timezone == self._SYSTEM_GENERATED_TIMEZONE_MARKER
        )

    @api.depends("check_time", "device_timezone", "verify_method", "check_type")
    def _compute_time_display(self):
        """Display the business Time column in the module timezone.

        Keep the rule intentionally simple for UI:
        - system-generated boundary logs keep the canonical conversion so
          16:59 UTC -> 23:59 and 17:00 UTC -> 00:00 in Asia/Ho_Chi_Minh;
        - real device logs show Check Time plus the module timezone offset.

        This matches the operational screen where Check Time is the UTC-storage
        clock value and Time is the human business time according to the module
        timezone, independent from the user's/browser's timezone.
        """
        module_tz = self._attendance_timezone_name()
        for rec in self:
            base_text = rec._format_check_time_in_module_timezone(rec.check_time)
            if not base_text:
                rec.time_display = False
                continue
            if rec._is_system_generated_log():
                rec.time_display = base_text
                continue
            try:
                base_dt = fields.Datetime.to_datetime(base_text) or date_parser.parse(base_text)
                offset = rec._timezone_offset_delta(module_tz, base_dt)
                rec.time_display = (base_dt + offset).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                rec.time_display = base_text

    @api.depends_context("uid", "tz")
    def _compute_module_time_runtime(self):
        """Show the current time according to the module timezone.

        This is a diagnostic display only. It is intentionally computed as text
        using entry_control.attendance_timezone so Odoo's user/browser timezone
        cannot shift the value again on screen.
        """
        tz_name = self._attendance_timezone_name()
        try:
            module_now = datetime.now(self._attendance_timezone()).replace(tzinfo=None)
            module_now_text = module_now.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            tz_name = self._DEFAULT_ATTENDANCE_TIMEZONE
            module_now_text = datetime.now(ZoneInfo(tz_name)).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
        for rec in self:
            rec.module_timezone_display = tz_name
            rec.module_time_now = module_now_text

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
    def _sanitize_attendance_timezone_name(self, value=None):
        """Return a valid IANA timezone name for module-level calculations."""
        tz_name = str(value or "").strip() or self._DEFAULT_ATTENDANCE_TIMEZONE
        try:
            ZoneInfo(tz_name)
            return tz_name
        except Exception:
            return self._DEFAULT_ATTENDANCE_TIMEZONE

    @api.model
    def _attendance_timezone_name(self):
        """Module business timezone.

        This setting is the single fallback timezone for Entry Control. It is
        independent from the current Odoo user's timezone and is used for:
        - controller timestamps that do not carry an explicit timezone;
        - system-generated Attendance Logs whose device_timezone is marker ``0``;
        - cron/current-business-day calculations.
        """
        try:
            value = self.env["ir.config_parameter"].sudo().get_param(self._CONFIG_ATTENDANCE_TIMEZONE)
        except Exception:
            value = False
        return self._sanitize_attendance_timezone_name(value)

    @api.model
    def _attendance_timezone(self):
        return ZoneInfo(self._attendance_timezone_name())

    @api.model
    def _normalize_device_timezone(self, tz_value=None):
        """Normalize device timezone text.

        Controller commonly sends offsets such as ``+07`` or ``+0700``. Store
        them as ``+07:00`` and use them as context to convert between Odoo UTC
        storage and Device Local Time for attendance calculation.
        """
        tz = str(tz_value or "").strip()
        if not tz:
            return self._attendance_timezone_name()
        if tz in (self._SYSTEM_GENERATED_TIMEZONE_MARKER, "0:00", "00:00"):
            return self._SYSTEM_GENERATED_TIMEZONE_MARKER
        if tz.upper() == "Z":
            return "+00:00"
        if len(tz) == 3 and tz[0] in "+-" and tz[1:].isdigit():
            return "%s:00" % tz
        if len(tz) == 5 and tz[0] in "+-" and tz[1:].isdigit():
            return "%s:%s" % (tz[:3], tz[3:])
        return tz

    @api.model
    def _tzinfo_from_device_timezone(self, tz_value=None):
        tz = self._normalize_device_timezone(tz_value)
        if tz == self._SYSTEM_GENERATED_TIMEZONE_MARKER:
            return self._attendance_timezone()
        if tz and tz[0:1] in ("+", "-"):
            sign = 1 if tz[0] == "+" else -1
            body = tz[1:]
            try:
                if ":" in body:
                    hh, mm = body.split(":", 1)
                else:
                    hh, mm = body[:2], body[2:] or "0"
                return timezone(sign * timedelta(hours=int(hh), minutes=int(mm)))
            except Exception:
                pass
        try:
            return ZoneInfo(tz)
        except Exception:
            return self._attendance_timezone()

    @api.model
    def _local_naive_to_utc(self, value, device_timezone=None):
        """Convert a device-local naive datetime into Odoo UTC-naive storage."""
        dt = fields.Datetime.to_datetime(value)
        if not dt:
            return False
        if dt.tzinfo:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        tzinfo = self._tzinfo_from_device_timezone(device_timezone)
        return dt.replace(tzinfo=tzinfo).astimezone(timezone.utc).replace(tzinfo=None)

    @api.model
    def _utc_naive_to_local(self, value, device_timezone=None):
        """Convert an Odoo UTC-naive datetime into Device Local Time."""
        dt = fields.Datetime.to_datetime(value)
        if not dt:
            return False
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(self._tzinfo_from_device_timezone(device_timezone)).replace(tzinfo=None)

    @api.model
    def _business_day_from_utc(self, value, device_timezone=None):
        """Return the Device Local business day from UTC-stored check_time."""
        local_dt = self._utc_naive_to_local(value, device_timezone)
        return local_dt.date() if local_dt else False

    @api.model
    def _business_day_from_log(self, log):
        """Return the business day of a log using that log's device_timezone."""
        return self._business_day_from_utc(log.check_time, log.device_timezone)

    @api.model
    def _business_day_bounds_utc(self, day, device_timezone=None):
        """Return UTC storage bounds for one Device Local business day."""
        day = fields.Date.to_date(day)
        local_start = datetime.combine(day, time.min)
        local_end = datetime.combine(day, time.max)
        return (
            self._local_naive_to_utc(local_start, device_timezone),
            self._local_naive_to_utc(local_end, device_timezone),
        )

    @api.model
    def _broad_utc_search_bounds_for_local_days(self, day_from, day_to):
        """Return a broad UTC range covering local days for any device offset.

        We cannot know every device timezone before searching, so wizard/cron
        first fetch a safe UTC window, then filters/groups records by each
        record's own device_timezone in Python.
        """
        day_from = fields.Date.to_date(day_from)
        day_to = fields.Date.to_date(day_to)
        return (
            datetime.combine(day_from - timedelta(days=2), time.min),
            datetime.combine(day_to + timedelta(days=2), time.max),
        )

    @api.model
    def _device_timezone_for_logs(self, logs):
        """Return the effective timezone for a grouped attendance day.

        System-generated rows intentionally store device_timezone = 0 for UI
        clarity. That marker must never become the timezone used to calculate
        business-day bounds; prefer a real device log timezone, then fall back
        to the module timezone setting.
        """
        for log in logs:
            tz = self._normalize_device_timezone(log.device_timezone)
            if tz and tz != self._SYSTEM_GENERATED_TIMEZONE_MARKER:
                return tz
        return self._attendance_timezone_name()

    @api.model
    def _business_now_date(self):
        return datetime.now(self._attendance_timezone()).date()

    @api.model
    def _parse_dt(self, value, timezone_hint=None):
        """Parse Controller check_time into Odoo UTC-naive storage.

        ``2026-05-27 09:12:05+07`` means 09:12:05 in the device timezone.
        Store it as UTC-naive check_time, and preserve ``+07:00`` in
        device_timezone so Create Attendances/Cron can group by Device Local Day.
        """
        raw = str(value or "").strip()
        if not raw:
            tz = self._normalize_device_timezone(timezone_hint or self._attendance_timezone_name())
            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            return now_utc, tz
        tz = self._extract_timezone_note_from_text(raw) or timezone_hint or self._attendance_timezone_name()
        tz = self._normalize_device_timezone(tz)
        try:
            check_time = self._normalize_check_time_value(raw, tz)
        except Exception:
            text = self._strip_timezone_note_from_text(raw).replace("T", " ").strip()
            dt = fields.Datetime.to_datetime(text) or date_parser.parse(text)
            check_time = self._local_naive_to_utc(dt.replace(tzinfo=None), tz) if dt else datetime.now(timezone.utc).replace(tzinfo=None)
        return check_time, tz

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
        check_raw = (
            data.get("check_time")
            or data.get("checkTime")
            or data.get("device_check_time")
            or data.get("deviceCheckTime")
            or data.get("local_check_time")
            or data.get("localCheckTime")
            or data.get("time")
            or data.get("timestamp")
        )
        timezone_hint = (
            data.get("device_timezone")
            or data.get("deviceTimezone")
            or data.get("timezone")
            or data.get("tz")
        )
        check_dt, parsed_tz = self._parse_dt(check_raw, timezone_hint=timezone_hint)
        if parsed_tz and not self._device_timezone_matches_module(parsed_tz, check_dt):
            _logger.warning(
                "[ENTRY CONTROL] Device timezone %s does not match module timezone %s for check_time=%s. "
                "The explicit controller offset is used for UTC storage; Time column displays in module timezone.",
                parsed_tz, self._attendance_timezone_name(), check_raw,
            )
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
            "device_timezone": parsed_tz,
            "employee_id": employee.id if employee else False,
            "direction": direction,
            "check_time": check_dt,
            "verify_method": verify_method if verify_method in dict(self._fields["verify_method"].selection) else "unknown",
            "verify_type": verify_type,
            "check_type": check_type,
            "sync_status": "success",
        }
        rec = self.sudo().with_context(entry_control_check_time_is_utc=True).create(vals)
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
        # local_dt is the intended MODULE-local boundary time, not device-local
        # time. System-generated 23:59 / 00:00 rows must be calculated only from
        # the module timezone setting, then saved with device_timezone = 0 as a
        # marker. Do not copy/use source_log.device_timezone here; otherwise the
        # same system row can shift when the real device log carries another
        # offset.
        # Example with module timezone Asia/Ho_Chi_Minh:
        #   2026-05-27 23:59 local => check_time 2026-05-27 16:59 UTC-naive.
        #   2026-05-28 00:00 local => check_time 2026-05-27 17:00 UTC-naive.
        calculation_tz = self._attendance_timezone_name()
        check_time = self._local_naive_to_utc(local_dt, calculation_tz)
        domain = [
            ("employee_id", "=", source_log.employee_id.id),
            ("check_time", "=", check_time),
            ("direction", "=", direction),
            ("verify_method", "=", "system_generated"),
        ]
        existing = self.sudo().search(domain, limit=1)
        if existing:
            if existing.device_timezone != self._SYSTEM_GENERATED_TIMEZONE_MARKER:
                existing.with_context(entry_control_check_time_is_utc=True).write({"device_timezone": self._SYSTEM_GENERATED_TIMEZONE_MARKER})
            return existing
        message = self._make_system_log_message(direction, local_dt, reason)
        vals = {
            "controller_id": source_log.controller_id.id if source_log.controller_id else False,
            "device_id": source_log.device_id.id if source_log.device_id else False,
            "serial_number": source_log.serial_number or (source_log.device_id.serial_number if source_log.device_id else ""),
            "device_timezone": self._SYSTEM_GENERATED_TIMEZONE_MARKER,
            "employee_id": source_log.employee_id.id,
            "direction": direction,
            "check_time": check_time,
            "verify_method": "system_generated",
            "verify_type": "system",
            "check_type": "system_generated",
            "sync_status": "success",
            "message": message,
        }
        return self.sudo().with_context(entry_control_check_time_is_utc=True).create(vals)

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
        """Create missing system boundary logs without rebuilding/deleting data.

        Simple workflow:
        - Do not delete existing Attendance Logs.
        - Do not delete/recreate old system logs on every run.
        - Only create a missing 23:59 Check Out for a completed business day
          whose last log is Check In.
        - Only create the carry-over 00:00 Check In for the next day when that
          next day has no real device log yet.
        - Never create 23:59/00:00 for the current or future business day.
        """
        Log = self.sudo()
        logs = Log.browse(logs.ids).filtered(lambda r: r.employee_id and r.check_time)
        if not logs:
            return logs

        employees = logs.mapped("employee_id")
        selected_days = [Log._business_day_from_log(l) for l in logs if l.check_time]
        selected_days = [d for d in selected_days if d]
        if not selected_days:
            return logs

        min_local_day = min(selected_days) - timedelta(days=1)
        max_local_day = max(selected_days)
        today = Log._business_now_date()
        search_from, search_to = Log._broad_utc_search_bounds_for_local_days(min_local_day, max_local_day + timedelta(days=1))

        affected = Log.browse()
        for employee in employees:
            # Keep direction continuous, but do not remove any database rows.
            affected |= Log._resequence_employee_logs(employee, search_from, search_to)

            day = min_local_day
            while day <= max_local_day:
                # No future system logs. Today's 23:59/next 00:00 must wait
                # until the day is completed.
                if day >= today:
                    day += timedelta(days=1)
                    continue

                emp_logs = Log.search([
                    ("employee_id", "=", employee.id),
                    ("check_time", ">=", search_from),
                    ("check_time", "<=", search_to),
                ], order="check_time asc, id asc")
                day_logs = emp_logs.filtered(lambda r, d=day: Log._business_day_from_log(r) == d).sorted(key=lambda r: (r.check_time, r.id))

                if day_logs and day_logs[-1].direction == "in":
                    last_log = day_logs[-1]
                    checkout_local = datetime.combine(day, time(23, 59, 0))
                    next_checkin_local = datetime.combine(day + timedelta(days=1), time(0, 0, 0))

                    affected |= Log._find_or_create_system_log(
                        last_log,
                        "out",
                        checkout_local,
                        _("missing Check Out at the end of the day"),
                    )

                    # After creating 23:59, resequence only; do not delete.
                    affected |= Log._resequence_employee_logs(employee, search_from, search_to)
                    emp_logs = Log.search([
                        ("employee_id", "=", employee.id),
                        ("check_time", ">=", search_from),
                        ("check_time", "<=", search_to),
                    ], order="check_time asc, id asc")
                    next_day_real_logs = emp_logs.filtered(
                        lambda r, nd=day + timedelta(days=1): r.verify_method != "system_generated" and Log._business_day_from_log(r) == nd
                    )
                    if not next_day_real_logs:
                        affected |= Log._find_or_create_system_log(
                            last_log,
                            "in",
                            next_checkin_local,
                            _("carry-over Check In for the next day after a system-generated 23:59 Check Out"),
                        )

                day += timedelta(days=1)

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

        # Search a broad UTC window, then action_sync_hr_attendance filters by
        # Device Local Day using each log's device_timezone.
        date_from, date_to = self._broad_utc_search_bounds_for_local_days(day_from, day_to)
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
        params.set_param(self._CONFIG_ATTENDANCE_TIMEZONE, self._attendance_timezone_name())
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

    @api.model
    def _hr_attendance_utc_from_log(self, log):
        """Return the exact UTC-naive value to write to hr.attendance.

        Attendance Logs.check_time is the canonical UTC-naive source.
        device_timezone is used to understand/display Device Local Time and to
        calculate business days, but it must not be added again before writing
        to hr.attendance because hr.attendance.check_in/check_out are also Odoo
        Datetime fields stored as UTC-naive.

        Examples with device_timezone +07:00:
        - Real device log: 03:29 UTC -> UI shows 10:29 local.
        - System 23:59 local: Attendance Logs stores 16:59 UTC and device_timezone 0 -> UI shows 23:59 local.
        - System 00:00 local: Attendance Logs stores 17:00 UTC previous day and device_timezone 0 -> UI shows 00:00 local.
        """
        if not log or not log.check_time:
            return False
        dt = fields.Datetime.to_datetime(log.check_time)
        return dt.replace(tzinfo=None) if dt else False

    def action_sync_hr_attendance(self):
        # Attendance calculation rule:
        # 1) Attendance Logs are the source of truth.
        # 2) If a business day ends with Check In, create system Attendance Logs:
        #      - Check Out at 23:59 of the same day
        #      - Check In at 00:00 of the next day
        # 3) Then create/update one CLOSED hr.attendance per Employee + Device Local business day:
        #      - check_in  = first Check In log of that business day
        #      - check_out = last Check Out log of that business day
        #    Values written to hr.attendance remain UTC-naive. The visible
        #    local time is produced by Odoo timezone display, not by adding
        #    device_timezone before writing.
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
        target_days = set(Log._business_day_from_log(l) for l in selected_logs if l.check_time)
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
        min_day = min(Log._business_day_from_log(l) for l in all_logs if l.check_time)
        max_day = max(Log._business_day_from_log(l) for l in all_logs if l.check_time)
        cleanup_from, cleanup_to = Log._broad_utc_search_bounds_for_local_days(min_day, max_day)
        Log._cleanup_entry_control_open_attendances(Attendance, employee_ids, cleanup_from, cleanup_to)

        # Only create/update hr.attendance for the requested business days.
        # _ensure_continuous_logs_for_days() intentionally looks one day before
        # and one day after the selected logs to maintain boundary rows, but the
        # summary Attendances must not leak outside the wizard/cron target range.
        selected_days = target_days
        grouped = defaultdict(list)
        for rec in all_logs:
            day = Log._business_day_from_log(rec)
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
            # Write UTC-naive values from Attendance Logs directly to hr.attendance.
            # Do NOT add device_timezone here. Odoo will apply the user's timezone
            # when displaying hr.attendance, so adding it here would double-shift time.
            #
            # Correct behavior:
            #   Real log:    check_time 03:29 + device_timezone +07 -> UI 10:29
            #   System log:  check_time 16:59 + device_timezone 0 -> UI 23:59
            #   System log:  check_time 17:00 previous day + device_timezone 0 -> UI 00:00 next day
            check_in = Log._hr_attendance_utc_from_log(first_in_log)
            check_out = Log._hr_attendance_utc_from_log(last_out_log) if last_out_log else False

            group_tz = Log._device_timezone_for_logs(day_logs)
            day_start, day_end = Log._business_day_bounds_utc(day, group_tz)
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
