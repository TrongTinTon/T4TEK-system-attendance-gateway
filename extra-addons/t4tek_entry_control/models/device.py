from odoo import api, fields, models


class EntryControlDevice(models.Model):
    _name = "entry.control.device"
    _description = "Gatekeeper Device"
    _rec_name = "serial_number"
    _order = "last_seen_at desc, id desc"

    controller_id = fields.Many2one("entry.control.controller", required=True, ondelete="cascade", index=True)
    attendance_timezone = fields.Selection(related="controller_id.attendance_timezone", string="Controller Timezone", readonly=True)
    attendance_timezone_offset = fields.Char(related="controller_id.attendance_timezone_offset", string="Current UTC Offset", readonly=True)
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
        # Device is offline because the Controller is online and explicitly
        # reported that the physical device cannot be reached.
        ("offline", "Offline"),
        # Device status is unknown because Odoo lost the Controller heartbeat,
        # so Odoo cannot trust whether the physical device is currently online
        # or offline. The next Controller device report will overwrite this.
        ("unknown", "Unknown"),
        ("deactive", "Deactive"),
    ], default="offline", index=True)
    active = fields.Boolean(default=True, index=True)
    # Actual device times reported by the local Controller.
    # last_seen_at / last_online_at are updated only when the device is detected online.
    # last_offline_at is the first detection time of the current offline period, not every report time.
    last_seen_at = fields.Datetime(readonly=True)
    last_online_at = fields.Datetime(readonly=True)
    last_offline_at = fields.Datetime(readonly=True)
    last_status_changed_at = fields.Datetime(readonly=True)
    # Server-side audit: when Odoo received the latest device report payload.
    last_reported_at = fields.Datetime(readonly=True)

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
    def _datetime_from_payload(self, payload, *keys):
        payload = dict(payload or {})
        for key in keys:
            value = payload.get(key)
            if not value:
                continue
            try:
                if isinstance(value, str):
                    text = value.strip()
                    if not text:
                        continue
                    # Controller sends UTC-naive server datetime: yyyy-MM-dd HH:mm:ss.
                    # Be tolerant of ISO-like strings with T/Z/offset.
                    text = text.replace("T", " ")
                    if text.endswith("Z"):
                        text = text[:-1]
                    # Strip a trailing timezone offset if present. Controller already normalized to UTC.
                    if len(text) > 19 and (text[19:20] in ("+", "-")):
                        text = text[:19]
                    if len(text) >= 19:
                        text = text[:19]
                    return fields.Datetime.to_datetime(text)
                return fields.Datetime.to_datetime(value)
            except Exception:
                continue
        return False

    @api.model
    def upsert_from_payload(self, controller, payload):
        payload = dict(payload or {})
        serial = self._serial_from_payload(payload)
        if not serial:
            return self.browse()
        connection_status = str(payload.get("connection_status") or payload.get("status") or "offline").strip().lower()
        active_status = str(payload.get("active_status") or "active").strip().lower()
        # Only the local Controller is allowed to confirm a real physical
        # online/offline state. Server-side heartbeat timeout uses "unknown"
        # instead of guessing that every device is physically offline.
        status = "deactive" if active_status == "deactive" else ("online" if connection_status == "online" else "offline")

        # Serial Number is the canonical device identity. Prefer an existing row
        # already assigned to the reporting Controller when old databases contain
        # duplicate serial rows. Otherwise use the canonical serial row and decide
        # below whether this report is allowed to claim/reassign the device.
        device = self.sudo().search([("controller_id", "=", controller.id), ("serial_number", "=", serial)], limit=1)
        if not device:
            device = self.sudo().search([("serial_number", "=", serial)], limit=1)

        received_at = fields.Datetime.now()
        payload_online_at = self._datetime_from_payload(payload, "last_online_at", "last_seen_at")
        payload_offline_at = self._datetime_from_payload(payload, "last_offline_at")
        payload_status_changed_at = self._datetime_from_payload(payload, "last_status_changed_at")

        # Cross-controller ownership rule:
        # - A physical device may be moved to another Controller. In that case an
        #   ONLINE report from the new Controller is strong evidence and should
        #   reassign the device to the new Controller.
        # - A stale OFFLINE report from the old Controller must NOT move the
        #   device back to the old Controller, otherwise Odoo will keep showing
        #   the old Controller after a real handover.
        # - If the incoming report is offline but includes a later last_online_at
        #   than Odoo currently has, accept it as a newer ownership signal.
        allow_controller_claim = True
        if device and device.controller_id and device.controller_id.id != controller.id:
            incoming_online_at = payload_online_at or (received_at if status == "online" else False)
            existing_online_at = device.last_online_at
            allow_controller_claim = False
            if status == "online":
                allow_controller_claim = True
            elif incoming_online_at and (not existing_online_at or incoming_online_at > existing_online_at):
                allow_controller_claim = True

            if not allow_controller_claim:
                # Ignore stale cross-controller offline/deactive reports. Do not
                # update status/offline time/IP because that would overwrite the
                # active Controller's view with stale data from the previous one.
                return device

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
            "status": status,
            "active": active_status != "deactive",
            "last_reported_at": received_at,
        }

        # Do not use report receive time as actual last_seen/offline time.
        # Actual times come from the Controller status probe history.
        if status == "online":
            online_at = payload_online_at or received_at
            vals.update({
                "last_seen_at": online_at,
                "last_online_at": online_at,
            })
        elif status == "offline":
            if payload_offline_at:
                vals["last_offline_at"] = payload_offline_at
            elif not device or device.status != "offline" or not device.last_offline_at:
                vals["last_offline_at"] = received_at

        previous_status = device.status if device else False
        if payload_status_changed_at:
            vals["last_status_changed_at"] = payload_status_changed_at
        elif not device or previous_status != status:
            vals["last_status_changed_at"] = received_at

        if device:
            device.write(vals)
        else:
            device = self.create(vals)
        return device
