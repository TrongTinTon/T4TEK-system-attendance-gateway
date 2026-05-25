from odoo import api, fields, models


class EntryControlDevice(models.Model):
    _name = "entry.control.device"
    _description = "Entry Control Device"
    _order = "last_seen_at desc, id desc"

    controller_id = fields.Many2one("entry.control.controller", required=True, ondelete="cascade", index=True)
    name = fields.Char(required=True)
    serial_number = fields.Char(required=True, index=True)
    model = fields.Char()
    firmware_version = fields.Char(string="Firmware")
    ip_address = fields.Char()
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
        ("controller_serial_unique", "unique(controller_id, serial_number)", "Serial Number must be unique per Controller."),
    ]

    @api.model
    def upsert_from_payload(self, controller, payload):
        payload = dict(payload or {})
        serial = str(payload.get("serial_number") or payload.get("serialNumber") or "").strip()
        if not serial:
            serial = str(payload.get("device_serial_number") or payload.get("deviceSerialNumber") or "").strip()
        if not serial:
            serial = str(payload.get("device_code") or payload.get("deviceCode") or payload.get("code") or "").strip()
        if not serial:
            return self.browse()
        connection_status = str(payload.get("connection_status") or payload.get("status") or "offline").strip().lower()
        active_status = str(payload.get("active_status") or "active").strip().lower()
        vals = {
            "controller_id": controller.id,
            "serial_number": serial,
            "name": payload.get("name") or payload.get("device_name") or serial,
            "model": payload.get("model"),
            "firmware_version": payload.get("firmware_version") or payload.get("firmware"),
            "ip_address": payload.get("ip_address"),
            "port": int(payload.get("port") or 4370),
            "machine_no": int(payload.get("machine_no") or 1),
            "comm_mode": payload.get("comm_mode") if payload.get("comm_mode") in ("tcp", "pull", "usb", "unknown") else "tcp",
            "status": "deactive" if active_status == "deactive" else ("online" if connection_status == "online" else "offline"),
            "active": active_status != "deactive",
            "last_seen_at": fields.Datetime.now(),
        }
        device = self.sudo().search([("controller_id", "=", controller.id), ("serial_number", "=", serial)], limit=1)
        if device:
            device.write(vals)
        else:
            device = self.create(vals)
        return device
