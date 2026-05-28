from odoo import api, fields, models


class EntryControlDevice(models.Model):
    _name = "entry.control.device"
    _description = "Gatekeeper Device"
    _rec_name = "serial_number"
    _order = "last_seen_at desc, id desc"

    controller_id = fields.Many2one("entry.control.controller", required=True, ondelete="cascade", index=True)
    name = fields.Char(string="Device Name", required=True)
    serial_number = fields.Char(string="Serial Number", required=True, index=True)
    model = fields.Char()
    firmware_version = fields.Char(string="Firmware")
    ip_address = fields.Char(string="Last IP Address")
    port = fields.Integer(default=4370)
    machine_no = fields.Integer(default=1)
    comm_mode = fields.Selection([
        ("tcp", "TCP/IP"),
        ("pull", "PULL"),
        ("usb", "USB"),
        ("unknown", "Unknown"),
    ], default="tcp", required=True)
    status = fields.Selection([
        ("online", "Online"),
        ("offline", "Offline"),
        ("deactive", "Deactive"),
    ], default="offline", index=True)
    active = fields.Boolean(default=True, index=True)
    last_seen_at = fields.Datetime(readonly=True)

    _sql_constraints = [
        ("serial_number_unique", "unique(serial_number)", "Serial Number must be unique."),
        # Kept for smooth upgrades from earlier builds; the global serial_number
        # constraint above is the real business identity.
        ("controller_serial_unique", "unique(controller_id, serial_number)", "Serial Number must be unique per Controller."),
    ]

    @api.model
    def _serial_from_payload(self, payload):
        payload = dict(payload or {})
        # Canonical identity is serial_number. Fallback names are accepted only
        # to tolerate older Controller builds; the value is still stored in the
        # canonical serial_number field. IP is never used as identity.
        return str(
            payload.get("serial_number")
            or payload.get("serialNumber")
            or payload.get("device_serial_number")
            or payload.get("deviceSerialNumber")
            or payload.get("sn")
            or ""
        ).strip()

    @api.model
    def upsert_from_payload(self, controller, payload):
        payload = dict(payload or {})
        serial = self._serial_from_payload(payload)
        if not serial:
            return self.browse()
        connection_status = str(payload.get("connection_status") or payload.get("status") or "offline").strip().lower()
        active_status = str(payload.get("active_status") or "active").strip().lower()
        vals = {
            "controller_id": controller.id,
            "serial_number": serial,
            "name": payload.get("name") or payload.get("device_name") or payload.get("deviceName") or serial,
            "model": payload.get("model"),
            "firmware_version": payload.get("firmware_version") or payload.get("firmwareVersion") or payload.get("firmware"),
            # Informational only. IP can overlap across sites/controllers and is
            # therefore not used for matching or Attendance Logs identity.
            "ip_address": payload.get("ip_address") or payload.get("ipAddress"),
            "port": int(payload.get("port") or 4370),
            "machine_no": int(payload.get("machine_no") or payload.get("machineNo") or 1),
            "comm_mode": payload.get("comm_mode") if payload.get("comm_mode") in ("tcp", "pull", "usb", "unknown") else "tcp",
            "status": "deactive" if active_status == "deactive" else ("online" if connection_status == "online" else "offline"),
            "active": active_status != "deactive",
            "last_seen_at": fields.Datetime.now(),
        }
        # Serial Number is the canonical device identity. If a physical device is
        # moved to another Controller, reassign it instead of creating a duplicate.
        device = self.sudo().search([("serial_number", "=", serial)], limit=1)
        if not device:
            # Tolerant fallback for old databases that may still contain duplicate
            # rows before the unique constraint is cleaned up.
            device = self.sudo().search([("controller_id", "=", controller.id), ("serial_number", "=", serial)], limit=1)
        if device:
            device.write(vals)
        else:
            device = self.create(vals)
        return device
