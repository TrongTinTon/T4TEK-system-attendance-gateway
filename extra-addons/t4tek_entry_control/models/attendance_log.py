from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
import logging
import re
from dateutil import parser as date_parser
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class EntryControlAttendanceLog(models.Model):
    _name = "entry.control.attendance.log"
    _description = "Gatekeeper Attendance Log"
    _order = "check_time desc, id desc"

    _DEFAULT_ATTENDANCE_TIMEZONE = "Asia/Ho_Chi_Minh"
    _CONFIG_ATTENDANCE_TIMEZONE = "entry_control.attendance_timezone"

    # Legacy key kept for backward compatibility with older module versions.
    _CONFIG_CRON_LAST_AT = "entry_control.last_daily_attendance_cron_at"
    _CONFIG_CRON_LAST_AT_UTC = "entry_control.last_daily_attendance_cron_at_utc"
    _CONFIG_CRON_LAST_AT_LOCAL = "entry_control.last_daily_attendance_cron_at_local"
    _CONFIG_CRON_LAST_DATE = "entry_control.last_daily_attendance_cron_date"
    _CONFIG_CRON_LAST_TIMEZONE = "entry_control.last_daily_attendance_cron_timezone"
    _CONFIG_CRON_LAST_DB_START = "entry_control.last_daily_attendance_cron_db_start"
    _CONFIG_CRON_LAST_DB_END = "entry_control.last_daily_attendance_cron_db_end"
    _CONFIG_CRON_LAST_LOG_COUNT = "entry_control.last_daily_attendance_cron_log_count"
    _CONFIG_CRON_LAST_EMPLOYEE_COUNT = "entry_control.last_daily_attendance_cron_employee_count"
    _CONFIG_CRON_LAST_CREATED_COUNT = "entry_control.last_daily_attendance_cron_created_count"
    _CONFIG_CRON_LAST_UPDATED_COUNT = "entry_control.last_daily_attendance_cron_updated_count"
    _CONFIG_CRON_LAST_FAILED_COUNT = "entry_control.last_daily_attendance_cron_failed_count"
    _CONFIG_CRON_LOCAL_RUN_TIME = "entry_control.daily_attendance_local_run_time"
    _DEFAULT_CRON_LOCAL_RUN_TIME = "00:00"

    @api.model
    def _attendance_timezone_name(self, controller=None):
        """Return the effective Gatekeeper business timezone.

        If a Controller is provided, its own Controller Timezone is the source
        of truth. The global setting remains only as a fallback/default for old
        records or controllers that have not been assigned a timezone yet.
        """
        if controller:
            try:
                controller = controller.sudo()
                tz_name = str(controller.attendance_timezone or "").strip()
                if tz_name:
                    ZoneInfo(tz_name)
                    return tz_name
            except Exception:
                _logger.warning(
                    "Invalid timezone on Controller %s. Falling back to Gatekeeper default.",
                    getattr(controller, "display_name", controller),
                )

        value = self.env["ir.config_parameter"].sudo().get_param(
            self._CONFIG_ATTENDANCE_TIMEZONE,
            self._DEFAULT_ATTENDANCE_TIMEZONE,
        )
        tz_name = str(value or "").strip() or self._DEFAULT_ATTENDANCE_TIMEZONE
        try:
            ZoneInfo(tz_name)
        except Exception:
            _logger.warning(
                "Invalid Gatekeeper default timezone config %r. Falling back to %s.",
                tz_name,
                self._DEFAULT_ATTENDANCE_TIMEZONE,
            )
            tz_name = self._DEFAULT_ATTENDANCE_TIMEZONE
            self.env["ir.config_parameter"].sudo().set_param(
                self._CONFIG_ATTENDANCE_TIMEZONE,
                tz_name,
            )
        return tz_name

    @api.model
    def _attendance_zoneinfo(self, controller=None):
        return ZoneInfo(self._attendance_timezone_name(controller))

    @api.model
    def _module_now(self):
        now_utc = fields.Datetime.now()
        now_local = now_utc.replace(tzinfo=timezone.utc).astimezone(self._attendance_zoneinfo())
        return now_utc, now_local

    @api.model
    def _controller_now(self, controller=None):
        now_utc = fields.Datetime.now()
        now_local = now_utc.replace(tzinfo=timezone.utc).astimezone(self._attendance_zoneinfo(controller))
        return now_utc, now_local

    @api.model
    def _local_day_utc_bounds(self, day, controller=None):
        day = fields.Date.to_date(day)
        tz = self._attendance_zoneinfo(controller)
        start_local = datetime.combine(day, time.min, tzinfo=tz)
        end_local = start_local + timedelta(days=1)
        db_start = start_local.astimezone(timezone.utc).replace(tzinfo=None)
        db_end = end_local.astimezone(timezone.utc).replace(tzinfo=None)
        return start_local, end_local, db_start, db_end

    @api.model
    def _format_timezone_offset(self, dt):
        """Return a readable UTC offset for an aware datetime."""
        if not dt or not dt.utcoffset():
            return "UTC+00:00"
        total_seconds = int(dt.utcoffset().total_seconds())
        sign = "+" if total_seconds >= 0 else "-"
        total_seconds = abs(total_seconds)
        hours, remainder = divmod(total_seconds, 3600)
        minutes = remainder // 60
        return "UTC%s%02d:%02d" % (sign, hours, minutes)

    @api.model
    def _format_module_local_datetime(self, dt, controller=None):
        """Format an aware datetime in the selected default/controller timezone."""
        if not dt:
            return ""
        tz_name = self._attendance_timezone_name(controller)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc).astimezone(self._attendance_zoneinfo(controller))
        else:
            dt = dt.astimezone(self._attendance_zoneinfo(controller))
        return "%s (%s, %s)" % (
            dt.strftime("%Y-%m-%d %H:%M:%S"),
            tz_name,
            self._format_timezone_offset(dt),
        )

    @api.model
    def _daily_cron_local_run_time(self):
        """Return local daily processing time as (hour, minute, text)."""
        value = self.env["ir.config_parameter"].sudo().get_param(
            self._CONFIG_CRON_LOCAL_RUN_TIME,
            self._DEFAULT_CRON_LOCAL_RUN_TIME,
        )
        text = str(value or self._DEFAULT_CRON_LOCAL_RUN_TIME).strip()
        match = re.match(r"^(\d{1,2}):(\d{2})$", text)
        if not match:
            text = self._DEFAULT_CRON_LOCAL_RUN_TIME
            match = re.match(r"^(\d{1,2}):(\d{2})$", text)
            self.env["ir.config_parameter"].sudo().set_param(self._CONFIG_CRON_LOCAL_RUN_TIME, text)
        hour = max(0, min(23, int(match.group(1))))
        minute = max(0, min(59, int(match.group(2))))
        normalized = "%02d:%02d" % (hour, minute)
        if normalized != text:
            self.env["ir.config_parameter"].sudo().set_param(self._CONFIG_CRON_LOCAL_RUN_TIME, normalized)
        return hour, minute, normalized

    @api.model
    def _controller_daily_due_info(self, controller, now_utc=None):
        """Compute whether one Controller is due for daily attendance processing.

        Odoo cron runs periodically in UTC. This helper converts the current UTC
        time into the Controller's business timezone, compares it with the local
        processing time, then returns the completed business date to process.
        """
        now_utc = now_utc or fields.Datetime.now()
        if not isinstance(now_utc, datetime):
            now_utc = fields.Datetime.to_datetime(now_utc)
        if now_utc.tzinfo is None:
            now_utc_aware = now_utc.replace(tzinfo=timezone.utc)
        else:
            now_utc_aware = now_utc.astimezone(timezone.utc)

        tz = self._attendance_zoneinfo(controller)
        local_now = now_utc_aware.astimezone(tz)
        hour, minute, run_time_text = self._daily_cron_local_run_time()
        local_due_at = datetime.combine(local_now.date(), time(hour, minute), tzinfo=tz)
        due_at_utc = local_due_at.astimezone(timezone.utc).replace(tzinfo=None)

        is_due = local_now >= local_due_at
        business_date = local_now.date() - timedelta(days=1) if is_due else False
        return {
            "is_due": is_due,
            "business_date": business_date,
            "timezone": self._attendance_timezone_name(controller),
            "local_now": local_now,
            "local_due_at": local_due_at,
            "due_at_utc": due_at_utc,
            "run_time": run_time_text,
        }

    @api.model
    def _write_daily_cron_metrics(self, **metrics):
        """Persist last cron diagnostics in ir.config_parameter.

        This is intentionally best-effort so a metrics write cannot break the
        attendance cron or a module upgrade.
        """
        try:
            ICP = self.env["ir.config_parameter"].sudo()
            last_at_utc = metrics.get("last_at_utc") or metrics.get("last_at")
            last_at_local = metrics.get("last_at_local")
            mapping = {
                # Keep writing the legacy key so older settings screens do not break during upgrades.
                self._CONFIG_CRON_LAST_AT: last_at_utc,
                self._CONFIG_CRON_LAST_AT_UTC: last_at_utc,
                self._CONFIG_CRON_LAST_AT_LOCAL: last_at_local,
                self._CONFIG_CRON_LAST_DATE: metrics.get("business_date"),
                self._CONFIG_CRON_LAST_TIMEZONE: metrics.get("timezone"),
                self._CONFIG_CRON_LAST_DB_START: metrics.get("db_start"),
                self._CONFIG_CRON_LAST_DB_END: metrics.get("db_end"),
                self._CONFIG_CRON_LAST_LOG_COUNT: metrics.get("log_count", 0),
                self._CONFIG_CRON_LAST_EMPLOYEE_COUNT: metrics.get("employee_count", 0),
                self._CONFIG_CRON_LAST_CREATED_COUNT: metrics.get("created_count", 0),
                self._CONFIG_CRON_LAST_UPDATED_COUNT: metrics.get("updated_count", 0),
                self._CONFIG_CRON_LAST_FAILED_COUNT: metrics.get("failed_count", 0),
                self._CONFIG_CRON_LOCAL_RUN_TIME: metrics.get("local_run_time") or self.env["ir.config_parameter"].sudo().get_param(self._CONFIG_CRON_LOCAL_RUN_TIME, self._DEFAULT_CRON_LOCAL_RUN_TIME),
            }
            for key, value in mapping.items():
                ICP.set_param(key, "" if value is None else str(value))
        except Exception:
            _logger.exception("Could not write Gatekeeper daily cron metrics.")

    # =========================================================================
    # FIELDS DEFINITION
    # =========================================================================
    controller_id = fields.Many2one("entry.control.controller", ondelete="set null", index=True)
    device_id = fields.Many2one("entry.control.device", string="Device Record", ondelete="set null", index=True)
    serial_number = fields.Char(string="Device", index=True, readonly=True)
    device_timezone = fields.Char(string="Device Timezone", readonly=True, index=True)
    employee_id = fields.Many2one("hr.employee", ondelete="set null", index=True)
    direction = fields.Selection([("in", "Check In"), ("out", "Check Out")], default="in", required=True, index=True)
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

    # =========================================================================
    # DATABASE INIT & UPGRADE CLEANUP
    # =========================================================================
    def init(self):
        """Dọn dẹp cấu trúc Database cũ khi upgrade module và cấu hình baseline."""
        self.env.cr.execute("ALTER TABLE IF EXISTS entry_control_attendance_log DROP CONSTRAINT IF EXISTS attendance_event_hash_unique")
        for column in (
            "event_hash", "pin", "direction_source", "device_direction", "device_check_type",
            "is_system_generated", "check_time_local", "device_check_time", "check_time_stored_display",
            "check_time_display", "check_time_db_utc", "check_time_device_local", "time_display",
        ):
            self.env.cr.execute('ALTER TABLE IF EXISTS entry_control_attendance_log DROP COLUMN IF EXISTS "%s"' % column)
            
        self.env.cr.execute("""
            UPDATE entry_control_attendance_log l
               SET serial_number = d.serial_number
              FROM entry_control_device d
             WHERE l.device_id = d.id
               AND (l.serial_number IS NULL OR l.serial_number = '')
        """)
        self.env.cr.execute('ALTER TABLE IF EXISTS entry_control_attendance_log DROP COLUMN IF EXISTS "device_serial_number"')
        self.env.cr.execute("""
            UPDATE entry_control_attendance_log
               SET device_timezone = NULL
             WHERE (verify_method = 'system_generated' OR check_type = 'system_generated')
               AND device_timezone IS NOT NULL
               AND device_timezone <> ''
        """)

    # =========================================================================
    # EMPLOYEE MAPPING HELPERS
    # =========================================================================
    @api.model
    def _employee_code_fields(self):
        Employee = self.env["hr.employee"]
        preferred = ["code", "employee_code", "identification_id"]
        return [fname for fname in preferred if fname in Employee._fields]

    @api.model
    def _employee_pin_fields(self):
        Employee = self.env["hr.employee"]
        preferred = ["pin", "entry_control_pin"]
        return [fname for fname in preferred if fname in Employee._fields]

    @api.model
    def find_employee_by_employee_id(self, employee_id):
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

    def find_employee_by_pin(self, pin):
        pin = str(pin or "").strip()
        if not pin:
            return self.env["hr.employee"].browse()
        Employee = self.env["hr.employee"].sudo()
        for field_name in self._employee_code_fields() + self._employee_pin_fields():
            emp = Employee.search([(field_name, "=", pin)], limit=1)
            if emp:
                return emp
        return Employee.browse()

    # =========================================================================
    # TIME NORMALIZATION
    # =========================================================================
    @api.model
    def _extract_timezone_note_from_text(self, value):
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
        raw = str(value or "").strip()
        if not raw:
            return raw
        if raw.endswith("Z") or raw.endswith("z"):
            return raw[:-1].strip()
        return re.sub(r"([+-]\d{2})(?::?\d{2})?$", "", raw).strip()

    @api.model
    def _normalize_check_time_value(self, value):
        """Normalize input to Odoo UTC-naive datetime.

        Current Controller builds send ``check_time`` as UTC-naive. If a legacy
        client sends an explicit offset/Z value, convert that instant to
        UTC-naive instead of stripping the offset.
        """
        if not value:
            return value
        if isinstance(value, str):
            raw = value.strip().replace("T", " ")
            try:
                if self._extract_timezone_note_from_text(raw):
                    parsed = date_parser.parse(raw)
                    if parsed and parsed.tzinfo:
                        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
                dt = fields.Datetime.to_datetime(self._strip_timezone_note_from_text(raw))
            except Exception:
                dt = date_parser.parse(raw)
                if dt and dt.tzinfo:
                    return dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt.replace(tzinfo=None) if dt else value
        dt = fields.Datetime.to_datetime(value)
        if dt and dt.tzinfo:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt.replace(tzinfo=None) if dt else value

    @api.model
    def _normalize_device_timezone(self, tz_value=None):
        tz = str(tz_value or "").strip()
        if tz in ("0", "0:00", "00:00") or not tz:
            return False
        if tz.upper() == "Z":
            return "+00:00"
        if len(tz) == 3 and tz[0] in "+-" and tz[1:].isdigit():
            return "%s:00" % tz
        if len(tz) == 5 and tz[0] in "+-" and tz[1:].isdigit():
            return "%s:%s" % (tz[:3], tz[3:])
        return tz

    @api.model
    def _business_day_bounds_local(self, day):
        """Backward-compatible local day bounds as naive local datetimes.

        Prefer _local_day_utc_bounds() for DB domains. The end value is the
        start of the next local day so callers can safely use < end.
        """
        day = fields.Date.to_date(day)
        start_local = datetime.combine(day, time.min)
        end_local = start_local + timedelta(days=1)
        return start_local, end_local

    # =========================================================================
    # ORM OVERRIDES (CREATE / WRITE) - Đã tối ưu hóa hàm kiểm tra
    # =========================================================================
    @api.model
    def _vals_are_system_generated(self, vals):
        vals = vals or {}
        # Chuẩn hóa chuỗi để check chính xác tuyệt đối không phụ thuộc vào chữ hoa/thường
        v_method = str(vals.get("verify_method") or "").strip().lower()
        c_type = str(vals.get("check_type") or "").strip().lower()
        return v_method == "system_generated" or c_type == "system_generated"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Sử dụng định danh rõ ràng qua lớp mô hình env[...] thay vì biến self chưa rõ ngữ cảnh
            if self.env["entry.control.attendance.log"]._vals_are_system_generated(vals):
                vals["device_timezone"] = False
            else:
                if vals.get("check_time") and not vals.get("device_timezone"):
                    tz_note = self._extract_timezone_note_from_text(vals.get("check_time"))
                    if tz_note:
                        vals["device_timezone"] = tz_note
                vals["device_timezone"] = self._normalize_device_timezone(vals.get("device_timezone"))

            if vals.get("check_time"):
                vals["check_time"] = self._normalize_check_time_value(vals.get("check_time"))
                
        return super(EntryControlAttendanceLog, self).create(vals_list)

    def write(self, vals):
        vals = dict(vals or {})
        explicit_system_generated = self._vals_are_system_generated(vals)
        existing_system_generated = bool(self) and all(rec._is_system_generated_log() for rec in self)
        system_generated = explicit_system_generated or existing_system_generated

        if system_generated:
            if explicit_system_generated or "device_timezone" in vals:
                vals["device_timezone"] = False
        else:
            if vals.get("check_time") and not vals.get("device_timezone"):
                tz_note = self._extract_timezone_note_from_text(vals.get("check_time"))
                if tz_note:
                    vals["device_timezone"] = tz_note
            if "device_timezone" in vals:
                vals["device_timezone"] = self._normalize_device_timezone(vals.get("device_timezone"))

        if vals.get("check_time"):
            vals["check_time"] = self._normalize_check_time_value(vals.get("check_time"))
        return super().write(vals)

    def _is_system_generated_log(self):
        self.ensure_one()
        def _norm(v): return (v or "").strip().lower().replace("-", "_").replace(" ", "_")
        return _norm(self.verify_method) == "system_generated" or _norm(self.check_type) == "system_generated"

    @api.model
    def _infer_direction(self, employee, check_dt):
        if not employee:
            return "in"
        previous_log = self.sudo().search([
            ("employee_id", "=", employee.id),
            ("check_time", "<", check_dt),
        ], order="check_time desc, id desc", limit=1)
        if previous_log and previous_log.direction == "in":
            return "out"
        return "in"

    # =========================================================================
    # INGESTION & DE-DUPLICATION (API DATA)
    # =========================================================================
    @api.model
    def _verify_method_from_type(self, verify_type):
        text = str(verify_type or "").strip().lower().replace("-", "_").replace(" ", "_")
        if not text:
            return "unknown"
        if any(x in text for x in ("finger", "fp", "vân", "van_tay")): return "fingerprint"
        if "face" in text: return "face"
        if "card" in text or "rf" in text: return "card"
        if any(x in text for x in ("pin", "password", "pwd")): return "pin" if "pin" in text else "password"
        try:
            code = int(float(text))
        except Exception:
            return "unknown"
        if code in (0, 3): return "password"
        if code == 1: return "fingerprint"
        if code in (2, 4): return "card"
        if code in (15, 16): return "face"
        return "mixed"

    @api.model
    def _find_existing_log(self, controller, device, serial_number, employee, check_time, check_type, verify_type):
        domain = [
            ("controller_id", "=", controller.id if controller else False),
            ("serial_number", "=", serial_number or ""),
            ("employee_id", "=", employee.id if employee else False),
            ("check_time", "=", check_time),
            ("check_type", "=", check_type or ""),
            ("verify_type", "=", verify_type or ""),
        ]
        return self.sudo().search(domain, limit=1)

    @api.model
    def ingest_direct_log(self, controller, data):
        data = dict(data or {})
        serial = data.get("serial_number")
        api_employee_id = str(data.get("employee_id") or data.get("employeeId") or "").strip()
        legacy_pin = str(data.get("pin") or "").strip()

        check_time = self._normalize_check_time_value(data.get("check_time"))
        check_type = str(data.get("check_type") or data.get("checkType") or "").strip()
        verify_type = str(data.get("verify_type") or data.get("verifyType") or "").strip()

        Device = self.env["entry.control.device"].sudo()
        device = Device.search([("serial_number", "=", serial)], limit=1) if serial else Device.browse()

        employee = self.find_employee_by_employee_id(api_employee_id)
        if not employee and legacy_pin:
            employee = self.find_employee_by_pin(legacy_pin)

        existing = self._find_existing_log(controller, device, serial, employee, check_time, check_type, verify_type)
        if existing:
            return existing, True

        vals = {
            "controller_id": controller.id,
            "device_id": device.id if device else False,
            "serial_number": serial,
            "employee_id": employee.id if employee else False,
            "direction": self._infer_direction(employee, check_time),
            "check_time": check_time,
            "device_timezone": self._normalize_device_timezone(
                data.get("device_timezone")
                or data.get("deviceTimezone")
                or self._extract_timezone_note_from_text(data.get("check_time"))
                or (controller._timezone_offset_text(check_time) if controller else False)
            ),
            "verify_method": data.get("verify_method") or data.get("verifyMethod") or self._verify_method_from_type(verify_type),
            "verify_type": verify_type,
            "check_type": check_type,
            "sync_status": "success",
        }
        return self.sudo().create(vals), False

    # =========================================================================
    # SYSTEM GENERATED LOG PRODUCTION
    # =========================================================================
    @api.model
    def _find_or_create_system_log(self, source_log, direction, local_dt, reason):
        """Create 23:59/00:00 boundary logs using source Controller timezone.

        local_dt is a controller-local business datetime. It is converted to
        Odoo's standard UTC-naive Datetime before being searched/created.
        """
        controller = source_log.controller_id if source_log and source_log.controller_id else None
        tz = self._attendance_zoneinfo(controller)
        if local_dt.tzinfo is None:
            local_aware = local_dt.replace(tzinfo=tz)
        else:
            local_aware = local_dt.astimezone(tz)
        check_time_normalized = local_aware.astimezone(timezone.utc).replace(tzinfo=None)

        # Đảm bảo chuyển đổi mốc datetime sang chuỗi chuẩn format của Odoo trước khi search biệt lập
        check_time_str = fields.Datetime.to_string(check_time_normalized) if isinstance(check_time_normalized, datetime) else check_time_normalized

        # Ép xung quyền hệ thống cao nhất tránh bộ lọc record rule chặn tạo dữ liệu
        LogSudo = self.env["entry.control.attendance.log"].sudo()

        domain = [
            ("controller_id", "=", source_log.controller_id.id if source_log.controller_id else False),
            ("employee_id", "=", source_log.employee_id.id),
            ("check_time", "=", check_time_str),
            ("verify_method", "=", "system_generated"),
            ("check_type", "=", "system_generated"),
            ("direction", "=", direction),
        ]
        
        existing = LogSudo.search(domain, limit=1)
        if existing:
            # Nếu đã tồn tại log hệ thống tạo trùng mốc này, trả về luôn để hàm gộp xử lý tiếp
            return existing

        vals = {
            "controller_id": source_log.controller_id.id if source_log.controller_id else False,
            "device_id": source_log.device_id.id if source_log.device_id else False,
            "serial_number": source_log.serial_number,
            "employee_id": source_log.employee_id.id,
            "direction": direction,
            "check_time": check_time_str,
            "device_timezone": False,
            "verify_method": "system_generated",
            "check_type": "system_generated",
            "message": _("Hệ thống tự tạo %s") % reason,
            "sync_status": "success",
        }
        
        # Tiến hành tạo mới bản ghi với quyền sudo cô lập hoàn toàn
        new_log = LogSudo.create(vals)
        return new_log

    # =========================================================================
    # UNIFIED DAILY HR ATTENDANCE SYNC
    # =========================================================================
    @api.model
    def _attendance_controllers_to_process(self):
        Controller = self.env["entry.control.controller"].sudo()
        controllers = Controller.search([("active", "=", True), ("status", "!=", "blocked")])
        if not controllers:
            controllers = Controller.search([])
        return controllers

    @api.model
    def _create_attendances_for_controller_day(self, controller, business_date):
        """Create/update hr.attendance for one Controller and one local day.

        The business day and system-generated 23:59/00:00 boundary logs are
        calculated in the Controller's own timezone. Database domains remain
        UTC-naive because Odoo Datetime fields are stored that way.
        """
        Log = self.env["entry.control.attendance.log"].sudo()
        HrAttendance = self.env["hr.attendance"].sudo()
        controller = controller.sudo() if controller else controller

        tz_name = Log._attendance_timezone_name(controller)
        start_local, end_local, db_start, db_end = Log._local_day_utc_bounds(business_date, controller)
        next_date = fields.Date.to_date(business_date) + timedelta(days=1)

        domain_base = []
        if controller:
            domain_base.append(("controller_id", "=", controller.id))
        else:
            domain_base.append(("controller_id", "=", False))

        _logger.info("===== GATEKEEPER CONTROLLER DAY DEBUG =====")
        _logger.info("Controller: %s", controller.display_name if controller else "<no controller>")
        _logger.info("Controller timezone: %s", tz_name)
        _logger.info("Business date: %s", business_date)
        _logger.info("Local range: %s -> %s", start_local, end_local)
        _logger.info("DB UTC range: %s -> %s", db_start, db_end)

        attendance_groups = Log.read_group(
            domain=domain_base + [
                ("check_time", ">=", db_start),
                ("check_time", "<", db_end),
                ("employee_id", "!=", False),
            ],
            fields=["employee_id"],
            groupby=["employee_id"],
        )

        employee_ids = [g["employee_id"][0] for g in attendance_groups if g.get("employee_id")]

        log_count = 0
        created_count = 0
        updated_count = 0
        failed_count = 0
        skipped_count = 0

        for emp_id in employee_ids:
            emp_logs = Log.search(domain_base + [
                ("employee_id", "=", emp_id),
                ("check_time", ">=", db_start),
                ("check_time", "<", db_end),
            ], order="check_time asc, id asc")

            if not emp_logs:
                skipped_count += 1
                continue

            log_count += len(emp_logs)
            last_log = emp_logs[-1]

            if last_log.direction == "in":
                Log._find_or_create_system_log(
                    source_log=last_log,
                    direction="out",
                    local_dt=datetime.combine(fields.Date.to_date(business_date), time(23, 59, 59)),
                    reason="23:59 Check Out",
                )

                Log._find_or_create_system_log(
                    source_log=last_log,
                    direction="in",
                    local_dt=datetime.combine(next_date, time(0, 0, 0)),
                    reason="00:00 Check In",
                )

                emp_logs = Log.search(domain_base + [
                    ("employee_id", "=", emp_id),
                    ("check_time", ">=", db_start),
                    ("check_time", "<", db_end),
                ], order="check_time asc, id asc")

            in_logs = emp_logs.filtered(lambda l: l.direction == "in")
            out_logs = emp_logs.filtered(lambda l: l.direction == "out")

            if not in_logs or not out_logs:
                skipped_count += 1
                _logger.warning(
                    "Skip employee %s on %s controller %s because IN or OUT log is missing.",
                    emp_id,
                    business_date,
                    controller.display_name if controller else "<no controller>",
                )
                continue

            first_in_log = in_logs[0]
            last_out_log = out_logs[-1]

            if last_out_log.check_time <= first_in_log.check_time:
                skipped_count += 1
                _logger.warning(
                    "Skip employee %s on %s controller %s because check_out <= check_in | IN=%s | OUT=%s",
                    emp_id,
                    business_date,
                    controller.display_name if controller else "<no controller>",
                    first_in_log.check_time,
                    last_out_log.check_time,
                )
                continue

            existing_attendance = HrAttendance.search([
                ("employee_id", "=", emp_id),
                ("check_in", ">=", db_start),
                ("check_in", "<", db_end),
            ], limit=1)

            vals = {
                "employee_id": emp_id,
                "check_in": first_in_log.check_time,
                "check_out": last_out_log.check_time,
            }

            try:
                if existing_attendance:
                    existing_attendance.write(vals)
                    attendance_rec = existing_attendance
                    updated_count += 1
                else:
                    attendance_rec = HrAttendance.create(vals)
                    created_count += 1

                emp_logs.write({
                    "hr_attendance_id": attendance_rec.id,
                    "sync_status": "success",
                    "error_message": False,
                })
            except Exception as e:
                failed_count += 1
                error_msg = str(e)
                _logger.error(
                    "Error creating/updating hr.attendance for employee %s on %s controller %s: %s",
                    emp_id,
                    business_date,
                    controller.display_name if controller else "<no controller>",
                    error_msg,
                )
                emp_logs.write({
                    "sync_status": "failed",
                    "error_message": error_msg,
                })

        return {
            "controller_id": controller.id if controller else False,
            "controller_name": controller.display_name if controller else "<no controller>",
            "timezone": tz_name,
            "business_date": fields.Date.to_string(business_date),
            "db_start": fields.Datetime.to_string(db_start),
            "db_end": fields.Datetime.to_string(db_end),
            "employee_count": len(employee_ids),
            "log_count": log_count,
            "created_count": created_count,
            "updated_count": updated_count,
            "skipped_count": skipped_count,
            "failed_count": failed_count,
        }

    @api.model
    def cron_create_daily_attendances(self):
        """Periodic UTC scheduler with per-Controller local due checks.

        The Odoo Scheduled Action should run frequently, for example every 15
        minutes. The cron itself does not represent any business timezone. Each
        Controller decides whether it is due by converting the current UTC time
        into its own ``attendance_timezone`` and comparing it with the configured
        local processing time. A processing ledger keeps one snapshot row per
        Controller and prevents duplicate processing of the same business date.
        """
        Log = self.env["entry.control.attendance.log"].sudo()
        Run = self.env["entry.control.attendance.cron.run"].sudo()
        controllers = Log._attendance_controllers_to_process()
        now_utc = fields.Datetime.now()

        total_employee_count = 0
        total_log_count = 0
        total_created_count = 0
        total_updated_count = 0
        total_failed_count = 0
        total_skipped_count = 0
        processed = []
        skipped_not_due = 0
        skipped_done = 0
        skipped_running = 0

        _logger.info("===== GATEKEEPER PERIODIC CRON START =====")
        _logger.info("Cron tick at UTC: %s", now_utc)

        for controller in controllers:
            due = Log._controller_daily_due_info(controller, now_utc)
            local_now = due.get("local_now")
            _logger.info(
                "Controller %s | tz=%s | local_now=%s | local_due_at=%s | due=%s",
                controller.display_name,
                due.get("timezone"),
                local_now,
                due.get("local_due_at"),
                due.get("is_due"),
            )

            if not due.get("is_due"):
                skipped_not_due += 1
                continue

            business_date = due.get("business_date")
            run = Run._get_or_create_controller_day_run(
                controller=controller,
                business_date=business_date,
                timezone_name=due.get("timezone"),
                local_run_time=due.get("run_time"),
                due_at_utc=due.get("due_at_utc"),
            )

            run_business_date = fields.Date.to_date(run.business_date) if run.business_date else False
            if run.status == "done" and run_business_date and run_business_date >= fields.Date.to_date(business_date):
                skipped_done += 1
                _logger.info(
                    "Skip controller %s business date %s because the single controller ledger is already done for %s.",
                    controller.display_name,
                    business_date,
                    run_business_date,
                )
                continue
            if run.status == "running" and not run._is_stale_running():
                skipped_running += 1
                _logger.info(
                    "Skip controller %s business date %s because ledger is already running.",
                    controller.display_name,
                    business_date,
                )
                continue

            run._mark_running(now_utc=now_utc, local_now=local_now)
            try:
                metrics = Log._create_attendances_for_controller_day(controller, business_date)
                metrics["local_run_time"] = due.get("run_time")
                metrics["due_at_utc"] = fields.Datetime.to_string(due.get("due_at_utc"))
                metrics["local_now"] = Log._format_module_local_datetime(local_now, controller)
                run._mark_done(metrics)
                processed.append(metrics)

                total_employee_count += int(metrics.get("employee_count") or 0)
                total_log_count += int(metrics.get("log_count") or 0)
                total_created_count += int(metrics.get("created_count") or 0)
                total_updated_count += int(metrics.get("updated_count") or 0)
                total_failed_count += int(metrics.get("failed_count") or 0)
                total_skipped_count += int(metrics.get("skipped_count") or 0)

                _logger.info(
                    "Cron processed controller %s | date=%s | timezone=%s | logs=%s | created=%s | updated=%s | skipped=%s | failed=%s",
                    metrics.get("controller_name"),
                    metrics.get("business_date"),
                    metrics.get("timezone"),
                    metrics.get("log_count"),
                    metrics.get("created_count"),
                    metrics.get("updated_count"),
                    metrics.get("skipped_count"),
                    metrics.get("failed_count"),
                )
            except Exception as e:
                run._mark_failed(str(e))
                total_failed_count += 1
                _logger.exception(
                    "Cron failed for controller %s business date %s.",
                    controller.display_name,
                    business_date,
                )

        timezone_summary = "; ".join(
            ["%s=%s" % (m.get("controller_name"), m.get("timezone")) for m in processed[:8]]
        )
        if len(processed) > 8:
            timezone_summary += "; ... +%s more" % (len(processed) - 8)
        business_date_summary = "; ".join(
            ["%s=%s" % (m.get("controller_name"), m.get("business_date")) for m in processed[:8]]
        )
        db_start_summary = "; ".join([m.get("db_start") or "" for m in processed[:3]])
        db_end_summary = "; ".join([m.get("db_end") or "" for m in processed[:3]])

        first_controller = controllers[:1] if controllers else False
        first_controller = first_controller[0] if first_controller else False
        first_local = now_utc.replace(tzinfo=timezone.utc).astimezone(Log._attendance_zoneinfo(first_controller)) if first_controller else now_utc.replace(tzinfo=timezone.utc)
        _h, _m, local_run_time = Log._daily_cron_local_run_time()

        Log._write_daily_cron_metrics(
            last_at_utc=fields.Datetime.to_string(now_utc),
            last_at_local=Log._format_module_local_datetime(first_local, first_controller),
            business_date=business_date_summary or "No controller due",
            timezone=timezone_summary or "Per-controller timezone; due=%s not_due=%s done=%s running=%s" % (len(processed), skipped_not_due, skipped_done, skipped_running),
            db_start=db_start_summary,
            db_end=db_end_summary,
            log_count=total_log_count,
            employee_count=total_employee_count,
            created_count=total_created_count,
            updated_count=total_updated_count,
            failed_count=total_failed_count,
            local_run_time=local_run_time,
        )

        _logger.info(
            "Cron completed | processed=%s | not_due=%s | already_done=%s | running=%s | employees=%s | logs=%s | created=%s | updated=%s | skipped=%s | failed=%s",
            len(processed),
            skipped_not_due,
            skipped_done,
            skipped_running,
            total_employee_count,
            total_log_count,
            total_created_count,
            total_updated_count,
            total_skipped_count,
            total_failed_count,
        )
        return True
