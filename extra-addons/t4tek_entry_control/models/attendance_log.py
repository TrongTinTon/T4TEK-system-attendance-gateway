import hashlib
from datetime import timezone
from dateutil import parser as date_parser
from odoo import api, fields, models, _


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    entry_control_pin = fields.Char(string="Entry Control PIN", copy=False, index=True)


class EntryControlAttendanceLog(models.Model):
    _name = "entry.control.attendance.log"
    _description = "Entry Control Attendance Log"
    _order = "check_time desc, id desc"

    controller_id = fields.Many2one("entry.control.controller", ondelete="set null", index=True)
    device_id = fields.Many2one("entry.control.device", ondelete="set null", index=True)
    employee_id = fields.Many2one("hr.employee", ondelete="set null", index=True)
    pin = fields.Char(index=True)

    direction = fields.Selection([("in", "Check In"), ("out", "Check Out")], default="in", required=True, index=True)
    direction_source = fields.Selection([("device", "Device"), ("software_inferred", "Software Inferred"), ("hybrid", "Hybrid")], default="hybrid", index=True)
    device_direction = fields.Selection([("in", "Device Check In"), ("out", "Device Check Out")], default="in", index=True)

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
    device_check_type = fields.Char(string="Device Check Type")

    hr_attendance_id = fields.Many2one("hr.attendance", string="HR Attendance", ondelete="set null", readonly=True, index=True)
    sync_status = fields.Selection([
        ("success", "Success"),
        ("failed", "Failed"),
        ("skipped", "Skipped"),
    ], default="success", index=True)
    error_message = fields.Text()
    event_hash = fields.Char(required=True, index=True, copy=False)
    created_at = fields.Datetime(default=fields.Datetime.now, readonly=True)

    _sql_constraints = [
        ("attendance_event_hash_unique", "unique(event_hash)", "Attendance Log already exists."),
    ]

    @api.model
    def _employee_pin_fields(self):
        Employee = self.env["hr.employee"]
        fields_ = []
        if "pin" in Employee._fields:
            fields_.append("pin")
        if "entry_control_pin" in Employee._fields:
            fields_.append("entry_control_pin")
        if "barcode" in Employee._fields:
            fields_.append("barcode")
        return fields_

    @api.model
    def find_employee_by_pin(self, pin):
        pin = str(pin or "").strip()
        if not pin:
            return self.env["hr.employee"].browse()
        Employee = self.env["hr.employee"].sudo()
        for field_name in self._employee_pin_fields():
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
    def _infer_direction(self, employee, check_dt, device_direction, check_type):
        # Hybrid mode: trust explicit out from device; if device only sends default check-in, infer from open attendance.
        if device_direction == "out":
            return "out", "device"
        if employee:
            open_att = self.env["hr.attendance"].sudo().search([
                ("employee_id", "=", employee.id),
                ("check_out", "=", False),
            ], order="check_in desc, id desc", limit=1)
            if open_att:
                return "out", "hybrid"
        return "in", "hybrid"

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
    def _event_hash(self, controller, serial, employee_id, pin, check_time, check_type, verify_type):
        text = "%s|%s|%s|%s|%s|%s|%s" % (
            controller.controller_uid if controller else "",
            serial or "",
            employee_id or "",
            pin or "",
            fields.Datetime.to_string(check_time) if check_time else "",
            check_type or "",
            verify_type or "",
        )
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @api.model
    def ingest_direct_log(self, controller, data):
        data = dict(data or {})
        serial = str(data.get("device_serial_number") or data.get("serial_number") or data.get("device_code") or data.get("deviceCode") or "").strip()
        employee_id = data.get("employee_id") or data.get("employeeId")
        pin = str(data.get("pin") or "").strip()
        check_raw = data.get("check_time") or data.get("checkTime") or data.get("time") or data.get("timestamp")
        check_dt, parsed_tz = self._parse_dt(check_raw)
        device_timezone = data.get("device_timezone") or data.get("deviceTimezone") or parsed_tz or ""
        check_type = str(data.get("check_type") or data.get("checkType") or "").strip()
        verify_type = str(data.get("verify_type") or data.get("verifyType") or "").strip()

        Device = self.env["entry.control.device"].sudo()
        device = Device.search([("controller_id", "=", controller.id), ("serial_number", "=", serial)], limit=1) if serial else Device.browse()
        Employee = self.env["hr.employee"].sudo()
        employee = Employee.browse(int(employee_id)).exists() if employee_id else Employee.browse()
        if not employee and pin:
            employee = self.find_employee_by_pin(pin)
        if employee and not pin:
            for fname in self._employee_pin_fields():
                pin = str(employee[fname] or "").strip()
                if pin:
                    break

        event_hash = data.get("event_hash") or data.get("eventHash") or self._event_hash(controller, serial, employee.id if employee else False, pin, check_dt, check_type, verify_type)
        existing = self.sudo().search([("event_hash", "=", event_hash)], limit=1)
        if existing:
            return existing, True

        device_direction = self._device_direction_from_check_type(check_type)
        direction, source = self._infer_direction(employee, check_dt, device_direction, check_type)
        verify_method = data.get("verify_method") or data.get("verifyMethod") or self._verify_method_from_type(verify_type)
        vals = {
            "controller_id": controller.id,
            "device_id": device.id if device else False,
            "employee_id": employee.id if employee else False,
            "pin": pin,
            "direction": direction,
            "direction_source": source,
            "device_direction": device_direction,
            "check_time": check_dt,
            "device_check_time": str(check_raw or ""),
            "device_timezone": device_timezone,
            "verify_method": verify_method if verify_method in dict(self._fields["verify_method"].selection) else "unknown",
            "verify_type": verify_type,
            "check_type": check_type,
            "device_check_type": check_type,
            "event_hash": event_hash,
            "sync_status": "success",
        }
        rec = self.sudo().create(vals)
        rec.action_sync_hr_attendance()
        return rec, False

    def action_sync_hr_attendance(self):
        Attendance = self.env["hr.attendance"].sudo()
        for rec in self:
            try:
                if not rec.employee_id:
                    raise ValueError(_("Cannot sync to Attendances: employee not found for PIN %s.") % (rec.pin or ""))
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
