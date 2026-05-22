from odoo import api, fields, models, _


class EntryControlUserDeviceStatus(models.Model):
    _name = "entry.control.user.device.status"
    _description = "Entry Control User Device Sync Status"
    _order = "last_reported_at desc, write_date desc, id desc"
    _rec_name = "display_name"

    display_name = fields.Char(compute="_compute_display_name", store=True)
    user_id = fields.Many2one("entry.control.user", string="Device User", ondelete="set null", index=True)
    pin = fields.Char(required=True, index=True)
    controller_id = fields.Many2one("entry.control.controller", required=True, ondelete="cascade", index=True)
    device_id = fields.Many2one("entry.control.device", string="Device", ondelete="set null", index=True)
    device_code = fields.Char(required=True, index=True)
    required_action = fields.Selection([
        ("create", "Create"),
        ("update", "Update"),
        ("delete", "Delete"),
        ("disable", "Disable"),
        ("enable", "Enable"),
        ("sync_user", "Sync User"),
        ("sync_fingerprint_set", "Sync Fingerprint Set"),
        ("push_fingerprint", "Push Fingerprint"),
        ("delete_fingerprint", "Delete Fingerprint"),
        ("pull_fingerprint", "Pull Fingerprint"),
    ], string="Last Action", index=True)
    sync_status = fields.Selection([
        ("pending", "Pending"),
        ("syncing", "Syncing"),
        ("success", "Success"),
        ("failed", "Failed"),
        ("ignored", "Ignored"),
    ], default="pending", required=True, index=True)
    actual_state = fields.Selection([
        ("unknown", "Unknown"),
        ("present", "Present on Device"),
        ("deleted", "Deleted from Device"),
        ("disabled", "Disabled on Device"),
        ("failed", "Failed"),
        ("missing", "Missing on Device"),
    ], default="unknown", required=True, index=True)
    last_message = fields.Char()
    last_error = fields.Text()
    last_local_job_id = fields.Char(index=True)
    last_synced_at = fields.Datetime(index=True)
    last_reported_at = fields.Datetime(index=True)
    controller_code = fields.Char(related="controller_id.controller_code", store=True, index=True)

    _sql_constraints = [
        ("controller_pin_device_unique", "unique(controller_id, pin, device_code)", "Each Controller / PIN / Device status must be unique."),
    ]

    @api.depends("pin", "device_code", "controller_id")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s / %s / %s" % (rec.pin or "-", rec.device_code or "-", rec.controller_id.controller_code or "-")

    @api.model
    def upsert_from_controller_result(self, controller, item):
        item = item or {}
        pin = str(item.get("pin") or "").strip()
        device_code = str(item.get("device_code") or item.get("deviceCode") or "").strip()
        if not pin or not device_code:
            raise ValueError("pin and device_code are required")

        User = self.env["entry.control.user"].sudo()
        Device = self.env["entry.control.device"].sudo()
        user = User.search([("pin", "=", pin)], limit=1)
        device = Device.search([("controller_id", "=", controller.id), ("device_code", "=", device_code)], limit=1)

        status = str(item.get("sync_status") or item.get("syncStatus") or "").strip().lower() or "pending"
        if status not in {"pending", "syncing", "success", "failed", "ignored"}:
            status = "failed" if status in {"error", "fail"} else "pending"
        actual_state = str(item.get("actual_state") or item.get("actualState") or "").strip().lower()
        if not actual_state:
            actual_state = "failed" if status == "failed" else ("present" if status == "success" else "unknown")
        if actual_state not in {"unknown", "present", "deleted", "disabled", "failed", "missing"}:
            actual_state = "unknown"

        required_action = str(item.get("required_action") or item.get("requiredAction") or item.get("action") or "").strip() or False
        vals = {
            "user_id": user.id if user else False,
            "pin": pin,
            "controller_id": controller.id,
            "device_id": device.id if device else False,
            "device_code": device_code,
            "required_action": required_action,
            "sync_status": status,
            "actual_state": actual_state,
            "last_message": str(item.get("message") or "")[:255],
            "last_error": item.get("error") or item.get("last_error") or item.get("lastError") or False,
            "last_local_job_id": str(item.get("local_job_id") or item.get("localJobId") or item.get("job_id") or item.get("jobId") or "") or False,
            "last_reported_at": fields.Datetime.now(),
        }
        synced_at = item.get("finished_at") or item.get("finishedAt") or item.get("synced_at") or item.get("syncedAt")
        if synced_at:
            try:
                vals["last_synced_at"] = fields.Datetime.to_datetime(synced_at)
            except Exception:
                vals["last_synced_at"] = fields.Datetime.now()
        elif status in ("success", "failed"):
            vals["last_synced_at"] = fields.Datetime.now()

        rec = self.sudo().search([
            ("controller_id", "=", controller.id),
            ("pin", "=", pin),
            ("device_code", "=", device_code),
        ], limit=1)
        if rec:
            rec.write(vals)
        else:
            rec = self.create(vals)
        return rec
