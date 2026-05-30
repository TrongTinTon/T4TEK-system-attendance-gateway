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
        if not value:
            return value
        if isinstance(value, str):
            raw = value.strip().replace("T", " ")
            raw = self._strip_timezone_note_from_text(raw)
            try:
                dt = fields.Datetime.to_datetime(raw)
            except Exception:
                dt = date_parser.parse(raw)
            return dt.replace(tzinfo=None) if dt else value
        dt = fields.Datetime.to_datetime(value)
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
        day = fields.Date.to_date(day)
        return (datetime.combine(day, time.min), datetime.combine(day, time(23, 59, 59)))

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
            "device_timezone": self._normalize_device_timezone(data.get("device_timezone") or data.get("deviceTimezone") or self._extract_timezone_note_from_text(data.get("check_time"))),
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
        """Khởi tạo log hệ thống biên ngày, chủ động TRỪ ĐI 7 GIỜ trước khi đưa vào Odoo ORM."""
        fixed_orm_dt = local_dt - timedelta(hours=7)
        check_time_normalized = self._normalize_check_time_value(fixed_orm_dt)
        
        # Đảm bảo chuyển đổi mốc datetime sang chuỗi chuẩn format của Odoo trước khi search biệt lập
        check_time_str = fields.Datetime.to_string(check_time_normalized) if isinstance(check_time_normalized, datetime) else check_time_normalized

        # Ép xung quyền hệ thống cao nhất tránh bộ lọc record rule chặn tạo dữ liệu
        LogSudo = self.env["entry.control.attendance.log"].sudo()

        domain = [
            ("employee_id", "=", source_log.employee_id.id),
            ("check_time", "=", check_time_str),
            ("verify_method", "=", "system_generated"),
            ("direction", "=", direction), # Thêm điều kiện hướng để phân biệt log IN / OUT tự tạo
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
    # UNIFIED DAILY HR ATTENDANCE SYNC (SỬA LỖI MÚI GIỜ KHI QUÉT)
    # =========================================================================
    @api.model
    def cron_create_daily_attendances(self):
        """Cron đồng bộ dữ liệu chấm công ngày hôm qua theo giờ Việt Nam."""

        vn_tz = ZoneInfo("Asia/Ho_Chi_Minh")

        Log = self.env["entry.control.attendance.log"].sudo()
        HrAttendance = self.env["hr.attendance"].sudo()

        # Odoo now là UTC-naive
        now_utc = fields.Datetime.now()

        # Convert UTC -> giờ Việt Nam
        now_vn = now_utc.replace(tzinfo=timezone.utc).astimezone(vn_tz)

        today_local = now_vn.date()
        yesterday_local = today_local - timedelta(days=1)

        # Range ngày hôm qua theo giờ Việt Nam:
        # 00:00 hôm qua -> 00:00 hôm nay
        start_local = datetime.combine(
            yesterday_local,
            time(0, 0, 0),
            tzinfo=vn_tz,
        )

        end_local = datetime.combine(
            today_local,
            time(0, 0, 0),
            tzinfo=vn_tz,
        )

        # Convert range Việt Nam sang UTC-naive để query DB Odoo
        db_start = start_local.astimezone(timezone.utc).replace(tzinfo=None)
        db_end = end_local.astimezone(timezone.utc).replace(tzinfo=None)

        _logger.info("===== CRON TIME DEBUG =====")
        _logger.info("Now UTC: %s", now_utc)
        _logger.info("Now VN: %s", now_vn)
        _logger.info("Today VN: %s", today_local)
        _logger.info("Yesterday VN: %s", yesterday_local)
        _logger.info("Start local VN: %s", start_local)
        _logger.info("End local VN: %s", end_local)
        _logger.info("DB UTC range: %s -> %s", db_start, db_end)

        attendance_groups = Log.read_group(
            domain=[
                ("check_time", ">=", db_start),
                ("check_time", "<", db_end),
                ("employee_id", "!=", False),
            ],
            fields=["employee_id"],
            groupby=["employee_id"],
        )

        employee_ids = [
            g["employee_id"][0]
            for g in attendance_groups
            if g.get("employee_id")
        ]

        _logger.info(
            "Cron Điểm Danh: Bắt đầu gộp cho %s nhân viên ngày %s",
            len(employee_ids),
            yesterday_local,
        )

        if not employee_ids:
            _logger.info(
                "Cron Điểm Danh: Không có dữ liệu log thuộc ngày %s | DB range %s -> %s",
                yesterday_local,
                db_start,
                db_end,
            )
            return True

        for emp_id in employee_ids:
            emp_logs = Log.search([
                ("employee_id", "=", emp_id),
                ("check_time", ">=", db_start),
                ("check_time", "<", db_end),
            ], order="check_time asc, id asc")

            if not emp_logs:
                continue

            last_log = emp_logs[-1]

            if last_log.direction == "in":
                self._find_or_create_system_log(
                    source_log=last_log,
                    direction="out",
                    local_dt=datetime.combine(yesterday_local, time(23, 59, 59)),
                    reason=""
                )

                self._find_or_create_system_log(
                    source_log=last_log,
                    direction="in",
                    local_dt=datetime.combine(today_local, time(0, 0, 0)),
                    reason=""
                )

                # Reload lại log ngày hôm qua, không lấy log 00:00 hôm nay
                emp_logs = Log.search([
                    ("employee_id", "=", emp_id),
                    ("check_time", ">=", db_start),
                    ("check_time", "<", db_end),
                ], order="check_time asc, id asc")

            in_logs = emp_logs.filtered(lambda l: l.direction == "in")
            out_logs = emp_logs.filtered(lambda l: l.direction == "out")

            if not in_logs or not out_logs:
                _logger.warning(
                    "Cron bỏ qua NV ID %s ngày %s vì thiếu IN hoặc OUT log",
                    emp_id,
                    yesterday_local,
                )
                continue

            first_in_log = in_logs[0]
            last_out_log = out_logs[-1]

            if last_out_log.check_time <= first_in_log.check_time:
                _logger.warning(
                    "Cron bỏ qua NV ID %s vì check_out <= check_in | IN=%s | OUT=%s",
                    emp_id,
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
                    _logger.info(
                        "Cron cập nhật hr.attendance ID %s cho NV ID %s",
                        attendance_rec.id,
                        emp_id,
                    )
                else:
                    attendance_rec = HrAttendance.create(vals)
                    _logger.info(
                        "Cron tạo hr.attendance ID %s cho NV ID %s",
                        attendance_rec.id,
                        emp_id,
                    )

                emp_logs.write({
                    "hr_attendance_id": attendance_rec.id,
                    "sync_status": "success",
                    "error_message": False,
                })

            except Exception as e:
                error_msg = str(e)
                _logger.error(
                    "Lỗi tạo/cập nhật hr.attendance cho NV ID %s ngày %s: %s",
                    emp_id,
                    yesterday_local,
                    error_msg,
                )
                emp_logs.write({
                    "sync_status": "failed",
                    "error_message": error_msg,
                })

        _logger.info(
            "Cron Điểm Danh: Hoàn tất xử lý gộp dữ liệu cho ngày %s",
            yesterday_local,
        )

        return True