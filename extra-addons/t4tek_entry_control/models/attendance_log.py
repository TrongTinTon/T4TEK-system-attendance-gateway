from datetime import datetime, timezone

from dateutil import parser as date_parser

from odoo import api, fields, models, _


class EntryControlAttendanceLog(models.Model):
    _name = "entry.control.attendance.log"
    _description = "Entry Control Attendance Log"
    _order = "check_time desc, id desc"

    controller_id = fields.Many2one("entry.control.controller", ondelete="set null", index=True)
    controller_code = fields.Char(related="controller_id.controller_code", store=True, index=True)
    device_id = fields.Many2one("entry.control.device", ondelete="set null", index=True)
    device_code = fields.Char(index=True)
    user_id = fields.Many2one("entry.control.user", ondelete="set null", index=True)
    employee_id = fields.Many2one("hr.employee", string="Employee", ondelete="set null", index=True)
    pin = fields.Char(required=True, index=True)

    # check_time is the original Controller/local device wall-clock time.
    # Example: Controller sends 2026-05-22 03:55:31+07 -> check_time stores 2026-05-22 03:55:31.
    # check_time_utc stores the normalized UTC value for hr.attendance/Odoo audit.
    check_time = fields.Datetime(string="Check Time (Device Local)", required=True, index=True)
    check_time_utc = fields.Datetime(string="Check Time UTC", readonly=True, index=True)
    check_time_raw = fields.Char(string="Raw Check Time", readonly=True)
    check_time_timezone = fields.Char(string="Source Timezone", readonly=True)

    # Device raw direction data is kept exactly for audit.
    # device_check_type = raw value sent by the Controller/device.
    # device_direction = direction mapped directly from device_check_type.
    # resolved_direction = final direction used by hr.attendance.
    # direction_source = how resolved_direction was decided.
    check_type = fields.Char(string="Check Type")
    device_check_type = fields.Char(string="Device Check Type", index=True)
    device_direction = fields.Selection([
        ("in", "Check In"),
        ("out", "Check Out"),
    ], string="Device Direction", default="in", index=True)
    resolved_direction = fields.Selection([
        ("in", "Check In"),
        ("out", "Check Out"),
    ], string="Resolved Direction", default="in", index=True)
    direction_source = fields.Selection([
        ("device", "Device"),
        ("software_inferred", "Software Inferred"),
        ("hybrid", "Hybrid"),
    ], string="Direction Source", default="device", index=True)
    attendance_direction = fields.Selection([
        ("in", "Check In"),
        ("out", "Check Out"),
    ], string="Direction", default="in", index=True)
    verify_type = fields.Char(string="Verify Code")
    verify_method = fields.Selection([
        ("fingerprint", "Fingerprint"),
        ("card", "Card/RF"),
        ("pin", "PIN"),
        ("password", "Password"),
        ("face", "Face"),
        ("palm", "Palm"),
        ("qr", "QR Code"),
        ("mixed", "Mixed"),
        ("manual", "Manual"),
        ("unknown", "Unknown"),
    ], string="Verify Method", default="unknown", index=True)
    verify_method_label = fields.Char(string="Verify Method Label", compute="_compute_verify_method_label", store=True)
    work_code = fields.Char()

    event_hash = fields.Char(required=True, index=True, copy=False)

    hr_attendance_id = fields.Many2one("hr.attendance", string="HR Attendance", ondelete="set null", readonly=True, index=True)
    sync_status = fields.Selection([
        ("received", "Received"),
        ("synced", "Synced to Attendances"),
        ("duplicate", "Duplicate"),
        ("failed", "Failed"),
    ], default="received", required=True, index=True)
    sync_message = fields.Char(string="Sync Message", readonly=True)
    sync_error_message = fields.Text(string="Error Message", readonly=True)
    synced_at = fields.Datetime(string="Synced At", readonly=True)

    _sql_constraints = [
        ("event_hash_unique", "unique(event_hash)", "Attendance event hash must be unique."),
    ]

    @api.depends("verify_method")
    def _compute_verify_method_label(self):
        labels = dict(self._fields["verify_method"].selection)
        for rec in self:
            rec.verify_method_label = labels.get(rec.verify_method or "unknown", "Unknown")

    @api.model
    def _normalize_tz_suffix(self, text):
        """dateutil.isoparse accepts +07:00 reliably; normalize +07 to +07:00."""
        text = (text or "").strip()
        if len(text) >= 3 and (text[-3] in ("+", "-")) and text[-2:].isdigit():
            return text + ":00"
        return text

    @api.model
    def _parse_controller_datetime_info(self, value):
        """Parse Controller/device datetime and preserve both local and UTC values.

        Odoo Datetime normally stores naive UTC. For Entry Control audit logs, the
        operator expects to see the same wall-clock time shown on the device.
        Therefore check_time uses the local wall-clock, while check_time_utc is
        kept for hr.attendance integration and technical reconciliation.
        """
        raw = str(value or "").strip()
        if not raw:
            now = fields.Datetime.now()
            return {
                "local": now,
                "utc": now,
                "raw": "",
                "timezone": "server_naive",
            }

        text = self._normalize_tz_suffix(raw.replace("Z", "+00:00"))
        try:
            if "T" in text or "+" in text[-6:] or "-" in text[-6:]:
                dt = date_parser.isoparse(text)
            else:
                dt = fields.Datetime.to_datetime(text)
        except Exception:
            dt = date_parser.parse(text)

        if dt.tzinfo:
            local_dt = dt.replace(tzinfo=None)
            utc_dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            tzinfo = dt.strftime("%z") or str(dt.tzinfo)
            if len(tzinfo) == 5:
                tzinfo = "%s:%s" % (tzinfo[:3], tzinfo[3:])
            return {
                "local": local_dt,
                "utc": utc_dt,
                "raw": raw,
                "timezone": tzinfo,
            }

        naive = dt.replace(tzinfo=None)
        return {
            "local": naive,
            "utc": naive,
            "raw": raw,
            "timezone": "naive",
        }

    @api.model
    def _parse_controller_datetime(self, value):
        # Backward compatible helper used by older code paths.
        return self._parse_controller_datetime_info(value)["local"]

    @api.model
    def _get_device_check_type(self, log):
        return str(
            log.get("check_type")
            or log.get("checkType")
            or log.get("att_state")
            or log.get("attState")
            or log.get("inout_mode")
            or log.get("inOutMode")
            or log.get("in_out_mode")
            or ""
        ).strip()

    @api.model
    def _detect_attendance_direction(self, log):
        raw = self._get_device_check_type(log)
        text = str(raw or "").strip().lower().replace("-", "_").replace(" ", "_")
        if text in ("1", "out", "check_out", "checkout", "break_out", "ot_out", "clock_out", "exit"):
            return "out"
        if text in ("2", "5"):
            # ZKTeco: 2=Break-Out, 5=OT-Out.
            return "out"
        return "in"

    @api.model
    def _infer_attendance_direction(self, employee, check_dt):
        """Infer direction from the current HR Attendance state.

        If the employee already has an open attendance before this punch, the
        next punch is treated as Check Out. Otherwise it is treated as Check In.
        This is used when devices always send ZKTeco AttState=0/Check-In Default.
        """
        if not employee or not check_dt:
            return "in"
        domain = [
            ("employee_id", "=", employee.id),
            ("check_out", "=", False),
            ("check_in", "<=", check_dt),
        ]
        open_attendance = self.env["hr.attendance"].sudo().search(domain, order="check_in desc, id desc", limit=1)
        return "out" if open_attendance else "in"

    @api.model
    def _get_attendance_direction_mode(self, controller):
        mode = (controller.attendance_direction_mode if controller and "attendance_direction_mode" in controller._fields else "hybrid") or "hybrid"
        if mode not in ("device", "software_inferred", "hybrid"):
            mode = "hybrid"
        return mode

    @api.model
    def _resolve_attendance_direction(self, controller, employee, check_dt, log, device_direction=None):
        """Return (resolved_direction, direction_source).

        - device: trust ZKTeco AttState/InOutMode.
        - software_inferred: ignore device direction and infer from open HR Attendance.
        - hybrid: explicit device Check-Out is trusted; device default/in values are
          resolved by software inference so machines that always send 0 can still
          produce Check In / Check Out pairs.
        """
        device_direction = device_direction or self._detect_attendance_direction(log)
        mode = self._get_attendance_direction_mode(controller)
        if mode == "device":
            return device_direction, "device"
        inferred = self._infer_attendance_direction(employee, check_dt)
        if mode == "software_inferred":
            return inferred, "software_inferred"
        if device_direction == "out":
            return "out", "device"
        return inferred, "hybrid"

    @api.model
    def _detect_verify_method(self, log):
        raw = log.get("verify_method") or log.get("verifyMethod") or log.get("verify_type") or log.get("verifyType") or log.get("verify_mode") or log.get("verifyMode") or ""
        text = str(raw or "").strip().lower().replace("-", "_").replace(" ", "_")
        if not text:
            return "unknown"
        if any(word in text for word in ("finger", "fp", "vân", "van_tay")):
            return "fingerprint"
        if any(word in text for word in ("face", "khuon_mat", "khuôn_mặt")):
            return "face"
        if "palm" in text:
            return "palm"
        if any(word in text for word in ("card", "rf", "mifare")):
            return "card"
        if "qr" in text:
            return "qr"
        if "pin" in text:
            return "pin"
        if any(word in text for word in ("pass", "pwd", "password")):
            return "password"
        try:
            code = int(float(text))
        except Exception:
            return "unknown"
        # ZKTeco SDK documents normal modes: 0=password, 1=fingerprint, 2=card.
        # Under multiple-verification tables, 2 may mean PIN, so keep PIN/card
        # distinguishable by raw verify_type and map the common values below.
        if code == 0:
            return "password"
        if code == 1:
            return "fingerprint"
        if code == 2:
            return "card"
        if code == 3:
            return "password"
        if code == 4:
            return "card"
        if code in (15, 16):
            return "face"
        if code in (100, 101):
            return "qr"
        return "mixed"

    @api.model
    def _find_employee_by_pin(self, pin):
        if not pin:
            return self.env["hr.employee"].browse()
        Employee = self.env["hr.employee"].sudo()
        if "pin" not in Employee._fields:
            return Employee.browse()
        return Employee.search([("pin", "=", str(pin).strip())], limit=1)

    @api.model
    def _prepare_log_values(self, controller, log, event_hash=None):
        log = dict(log or {})
        device_code = log.get("device_code") or log.get("deviceCode")
        pin = str(log.get("pin") or "").strip()
        check_raw = log.get("check_time") or log.get("checkTime") or log.get("time") or log.get("timestamp")
        dt_info = self._parse_controller_datetime_info(check_raw)

        device = self.env["entry.control.device"].sudo().search([
            ("controller_id", "=", controller.id),
            ("device_code", "=", device_code),
        ], limit=1) if device_code else self.env["entry.control.device"].browse()
        user = self.env["entry.control.user"].sudo().search([("pin", "=", pin)], limit=1)
        employee = user.employee_id if user and user.employee_id else self._find_employee_by_pin(pin)
        device_check_type = self._get_device_check_type(log)
        device_direction = self._detect_attendance_direction(log)
        resolved_direction, direction_source = self._resolve_attendance_direction(
            controller,
            employee,
            dt_info["utc"] or dt_info["local"],
            log,
            device_direction=device_direction,
        )
        return {
            "controller_id": controller.id,
            "device_id": device.id if device else False,
            "device_code": device_code,
            "user_id": user.id if user else False,
            "employee_id": employee.id if employee else False,
            "pin": pin,
            "check_time": dt_info["local"],
            "check_time_utc": dt_info["utc"],
            "check_time_raw": dt_info["raw"],
            "check_time_timezone": dt_info["timezone"],
            "check_type": device_check_type,
            "device_check_type": device_check_type,
            "device_direction": device_direction,
            "resolved_direction": resolved_direction,
            "direction_source": direction_source,
            # Backward-compatible field used by existing views/code.
            "attendance_direction": resolved_direction,
            "verify_type": str(log.get("verify_type") or log.get("verifyType") or log.get("verify_mode") or log.get("verifyMode") or ""),
            "verify_method": self._detect_verify_method(log),
            "work_code": str(log.get("work_code") or log.get("workCode") or ""),
            "event_hash": event_hash,
            "sync_status": "received",
            "sync_message": False,
            "sync_error_message": False,
        }

    @api.model
    def _build_event_hash(self, controller_code, log):
        return "%s|%s|%s|%s|%s" % (
            controller_code or "",
            log.get("device_code") or log.get("deviceCode") or "",
            log.get("pin") or "",
            log.get("check_time") or log.get("checkTime") or log.get("time") or log.get("timestamp") or "",
            log.get("verify_type") or log.get("verifyType") or log.get("verify_mode") or log.get("verifyMode") or "",
        )

    @api.model
    def ingest_from_event(self, event):
        payload = event.payload or {}
        log = payload.get("log") or payload
        event_hash = log.get("event_hash") or payload.get("event_hash") or self._build_event_hash(event.controller_code, log)
        existing = self.sudo().search([("event_hash", "=", event_hash)], limit=1)
        if existing:
            existing.write({"sync_status": "duplicate", "sync_message": _("Duplicate attendance event.")})
            return existing
        record = self.sudo().create(self._prepare_log_values(event.controller_id, log, event_hash=event_hash))
        record.action_sync_hr_attendance()
        return record

    @api.model
    def ingest_direct_log(self, controller, log):
        """Create/update Attendance Log directly from Controller API.

        Controller sends pulled attendance batches directly to
        /api/entry_control/v1/attendance/logs/push. The log is then synced to
        Odoo Attendances (hr.attendance), and the result is stored on the log so
        the server can see controller, device, status, and failure message.
        """
        log = dict(log or {})
        event_hash = log.get("event_hash") or log.get("eventHash") or self._build_event_hash(controller.controller_code, log)
        existing = self.sudo().search([("event_hash", "=", event_hash)], limit=1)
        if existing:
            if existing.sync_status == "received":
                existing.action_sync_hr_attendance()
            if existing.sync_status != "failed":
                existing.write({"sync_status": "duplicate", "sync_message": _("Duplicate attendance event; original log already exists.")})
            return existing, True

        record = self.sudo().create(self._prepare_log_values(controller, log, event_hash=event_hash))
        record.action_sync_hr_attendance()
        return record, False

    def _hr_attendance_values_for_checkin(self):
        self.ensure_one()
        return {
            "employee_id": self.employee_id.id,
            "check_in": self.check_time_utc or self.check_time,
            "entry_control_in_log_id": self.id,
            "entry_control_controller_id": self.controller_id.id if self.controller_id else False,
            "entry_control_device_id": self.device_id.id if self.device_id else False,
            "entry_control_in_method": self.verify_method or "unknown",
        }

    def action_sync_hr_attendance(self):
        Attendance = self.env["hr.attendance"].sudo()
        for rec in self:
            try:
                if rec.hr_attendance_id:
                    rec.write({
                        "sync_status": "synced",
                        "sync_message": _("Already linked to Attendances."),
                        "sync_error_message": False,
                        "synced_at": fields.Datetime.now(),
                    })
                    continue
                if not rec.employee_id:
                    employee = rec._find_employee_by_pin(rec.pin)
                    if employee:
                        rec.employee_id = employee.id
                if not rec.employee_id:
                    raise ValueError(_("Cannot sync to Attendances: no Employee found for PIN %s.") % (rec.pin or ""))

                check_dt = rec.check_time_utc or rec.check_time
                if not check_dt:
                    raise ValueError(_("Cannot sync to Attendances: missing check_time."))

                open_attendance = Attendance.search([
                    ("employee_id", "=", rec.employee_id.id),
                    ("check_out", "=", False),
                ], order="check_in desc, id desc", limit=1)

                if (rec.resolved_direction or rec.attendance_direction) == "out":
                    if not open_attendance:
                        raise ValueError(_("Cannot set check-out: Employee %s has no open attendance.") % rec.employee_id.display_name)
                    if open_attendance.check_in and check_dt < open_attendance.check_in:
                        raise ValueError(_("Cannot set check-out before check-in. Check-in=%s, check-out=%s.") % (open_attendance.check_in, check_dt))
                    vals = {
                        "check_out": check_dt,
                        "entry_control_out_log_id": rec.id,
                        "entry_control_out_method": rec.verify_method or "unknown",
                    }
                    if "entry_control_controller_id" in Attendance._fields and not open_attendance.entry_control_controller_id:
                        vals["entry_control_controller_id"] = rec.controller_id.id if rec.controller_id else False
                    if "entry_control_device_id" in Attendance._fields and not open_attendance.entry_control_device_id:
                        vals["entry_control_device_id"] = rec.device_id.id if rec.device_id else False
                    open_attendance.write(vals)
                    rec.write({
                        "hr_attendance_id": open_attendance.id,
                        "sync_status": "synced",
                        "sync_message": _("Synced as HR Attendance check-out."),
                        "sync_error_message": False,
                        "synced_at": fields.Datetime.now(),
                    })
                    continue

                if open_attendance:
                    rec.write({
                        "hr_attendance_id": open_attendance.id,
                        "sync_status": "synced",
                        "sync_message": _("Employee already has an open HR Attendance; log linked without creating a second check-in."),
                        "sync_error_message": False,
                        "synced_at": fields.Datetime.now(),
                    })
                    continue

                attendance = Attendance.create(rec._hr_attendance_values_for_checkin())
                rec.write({
                    "hr_attendance_id": attendance.id,
                    "sync_status": "synced",
                    "sync_message": _("Synced as HR Attendance check-in."),
                    "sync_error_message": False,
                    "synced_at": fields.Datetime.now(),
                })
            except Exception as error:
                rec.write({
                    "sync_status": "failed",
                    "sync_message": _("Failed to sync to Attendances."),
                    "sync_error_message": str(error),
                })
        return True


class HrAttendance(models.Model):
    _inherit = "hr.attendance"

    entry_control_in_log_id = fields.Many2one("entry.control.attendance.log", string="Entry Control Check-in Log", readonly=True, copy=False)
    entry_control_out_log_id = fields.Many2one("entry.control.attendance.log", string="Entry Control Check-out Log", readonly=True, copy=False)
    entry_control_controller_id = fields.Many2one("entry.control.controller", string="Entry Control Controller", readonly=True, copy=False)
    entry_control_device_id = fields.Many2one("entry.control.device", string="Entry Control Device", readonly=True, copy=False)
    entry_control_in_method = fields.Selection([
        ("fingerprint", "Fingerprint"),
        ("card", "Card/RF"),
        ("pin", "PIN"),
        ("password", "Password"),
        ("face", "Face"),
        ("palm", "Palm"),
        ("qr", "QR Code"),
        ("mixed", "Mixed"),
        ("manual", "Manual"),
        ("unknown", "Unknown"),
    ], string="Entry Method In", readonly=True, copy=False)
    entry_control_out_method = fields.Selection([
        ("fingerprint", "Fingerprint"),
        ("card", "Card/RF"),
        ("pin", "PIN"),
        ("password", "Password"),
        ("face", "Face"),
        ("palm", "Palm"),
        ("qr", "QR Code"),
        ("mixed", "Mixed"),
        ("manual", "Manual"),
        ("unknown", "Unknown"),
    ], string="Entry Method Out", readonly=True, copy=False)
