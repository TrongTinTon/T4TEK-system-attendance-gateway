from datetime import timezone
from dateutil import parser as date_parser
from odoo import api, fields, models, _, SUPERUSER_ID



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
    def _infer_direction(self, employee, check_dt, device_direction):
        # Hybrid behavior without storing source: trust explicit out from device;
        # otherwise infer from open hr.attendance.
        if device_direction == "out":
            return "out"
        if employee:
            open_att = self.env["hr.attendance"].sudo().search([
                ("employee_id", "=", employee.id),
                ("check_out", "=", False),
            ], order="check_in desc, id desc", limit=1)
            if open_att:
                return "out"
        return "in"

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

        device_direction = self._device_direction_from_check_type(check_type)
        direction = self._infer_direction(employee, check_dt, device_direction)
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
        rec.action_sync_hr_attendance()
        return rec, False

    def action_sync_hr_attendance(self):
        # API routes are auth=none, so the request env can have no normal
        # singleton user. hr.attendance may access env.user internally during
        # create/write; use an explicit superuser environment to avoid
        # "Expected singleton: res.users()" while still writing the same records.
        super_env = api.Environment(self.env.cr, SUPERUSER_ID, dict(self.env.context or {}))
        Attendance = super_env["hr.attendance"].sudo()
        Log = super_env[self._name].sudo()
        for original_rec in self:
            rec = Log.browse(original_rec.id)
            try:
                if not rec.employee_id:
                    raise ValueError(_("Cannot sync to Attendances: employee not found for this attendance log."))
                check_dt = rec.check_time
                open_att = Attendance.search([
                    ("employee_id", "=", rec.employee_id.id),
                    ("check_out", "=", False),
                ], order="check_in desc, id desc", limit=1)
                if rec.direction == "out":
                    if not open_att:
                        raise ValueError(_("Cannot check out: no open attendance for %s.") % rec.employee_id.display_name)
                    if open_att.check_in and check_dt < open_att.check_in:
                        raise ValueError(_("Cannot check out before check in."))
                    open_att.write({"check_out": check_dt})
                    rec.write({"hr_attendance_id": open_att.id, "sync_status": "success", "error_message": False})
                else:
                    if open_att:
                        rec.write({"hr_attendance_id": open_att.id, "sync_status": "skipped", "error_message": _("Employee already has an open attendance; log linked only.")})
                    else:
                        att = Attendance.create({"employee_id": rec.employee_id.id, "check_in": check_dt})
                        rec.write({"hr_attendance_id": att.id, "sync_status": "success", "error_message": False})
            except Exception as e:
                rec.write({"sync_status": "failed", "error_message": str(e)})
        return True
