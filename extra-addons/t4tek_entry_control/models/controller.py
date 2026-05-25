import hashlib
import secrets
from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class EntryControlController(models.Model):
    _name = "entry.control.controller"
    _description = "Entry Control Controller"
    _order = "last_heartbeat_at desc, id desc"

    controller_uid = fields.Char(string="Controller ID", required=True, index=True, copy=False)
    # Backward-compatible alias for existing controller source/UI names.
    controller_code = fields.Char(string="Controller Code", compute="_compute_controller_code", inverse="_inverse_controller_code", store=True, index=True)
    name = fields.Char(required=True, default="New Controller")
    secret_key = fields.Char(string="Secret Key", required=True, copy=False)

    last_sync_at = fields.Datetime(string="Last Sync At", readonly=True)
    last_heartbeat_at = fields.Datetime(string="Last Heartbeat At", readonly=True)
    status = fields.Selection([
        ("online", "Online"),
        ("offline", "Offline"),
        ("blocked", "Blocked"),
    ], default="offline", required=True, index=True)
    active = fields.Boolean(default=True, index=True)
    note = fields.Text()

    token_hash = fields.Char(copy=False, readonly=True)
    token_hint = fields.Char(copy=False, readonly=True)
    token_expires_at = fields.Datetime(copy=False, readonly=True)
    refresh_token_hash = fields.Char(copy=False, readonly=True)
    refresh_token_expires_at = fields.Datetime(copy=False, readonly=True)
    last_auth_at = fields.Datetime(readonly=True)
    last_error = fields.Text(readonly=True)

    device_ids = fields.One2many("entry.control.device", "controller_id", string="Devices")
    employee_sync_ids = fields.One2many("entry.control.employee.sync", "controller_id", string="Employees Synced")
    attendance_log_ids = fields.One2many("entry.control.attendance.log", "controller_id", string="Attendance Logs")
    device_count = fields.Integer(compute="_compute_counts")
    employee_sync_count = fields.Integer(compute="_compute_counts")
    attendance_log_count = fields.Integer(compute="_compute_counts")

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    _sql_constraints = [
        ("controller_uid_unique", "unique(controller_uid)", "Controller ID must be unique."),
    ]

    @api.depends("controller_uid")
    def _compute_controller_code(self):
        for rec in self:
            rec.controller_code = rec.controller_uid

    def _inverse_controller_code(self):
        for rec in self:
            if rec.controller_code and rec.controller_code != rec.controller_uid:
                rec.controller_uid = rec.controller_code

    @api.depends("device_ids", "employee_sync_ids", "attendance_log_ids")
    def _compute_counts(self):
        Device = self.env["entry.control.device"].sudo()
        EmpSync = self.env["entry.control.employee.sync"].sudo()
        Log = self.env["entry.control.attendance.log"].sudo()
        for rec in self:
            rec.device_count = Device.search_count([("controller_id", "=", rec.id)])
            rec.employee_sync_count = EmpSync.search_count([("controller_id", "=", rec.id)])
            rec.attendance_log_count = Log.search_count([("controller_id", "=", rec.id)])

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("controller_uid"):
                vals["controller_uid"] = str(vals["controller_uid"]).strip().upper()
            if not vals.get("secret_key"):
                vals["secret_key"] = self._new_secret_key()
            if not vals.get("name"):
                vals["name"] = vals.get("controller_uid") or "New Controller"
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals or {})
        if vals.get("controller_uid"):
            vals["controller_uid"] = str(vals["controller_uid"]).strip().upper()
        return super().write(vals)

    @api.model
    def _hash_token(self, token):
        return hashlib.sha256((token or "").encode("utf-8")).hexdigest()

    @api.model
    def _new_secret_key(self):
        return secrets.token_urlsafe(32)

    @api.model
    def _new_token(self):
        return secrets.token_urlsafe(48)

    def check_access_token(self, token):
        self.ensure_one()
        if not token or not self.token_hash:
            return False
        if self.token_expires_at and self.token_expires_at <= fields.Datetime.now():
            return False
        return self._hash_token(token) == self.token_hash

    def check_refresh_token(self, token):
        self.ensure_one()
        if not token or not self.refresh_token_hash:
            return False
        if self.refresh_token_expires_at and self.refresh_token_expires_at <= fields.Datetime.now():
            return False
        return self._hash_token(token) == self.refresh_token_hash

    def issue_tokens(self):
        self.ensure_one()
        if not self.active or self.status == "blocked":
            raise UserError(_("Controller is inactive or blocked."))
        access_token = self._new_token()
        refresh_token = self._new_token()
        now = fields.Datetime.now()
        access_ttl = int(self.env["ir.config_parameter"].sudo().get_param("entry_control.access_token_ttl_seconds", "3600") or 3600)
        refresh_ttl = int(self.env["ir.config_parameter"].sudo().get_param("entry_control.refresh_token_ttl_seconds", "2592000") or 2592000)
        self.sudo().write({
            "token_hash": self._hash_token(access_token),
            "token_hint": "%s...%s" % (access_token[:8], access_token[-6:]),
            "token_expires_at": now + timedelta(seconds=max(300, access_ttl)),
            "refresh_token_hash": self._hash_token(refresh_token),
            "refresh_token_expires_at": now + timedelta(seconds=max(3600, refresh_ttl)),
            "last_auth_at": now,
            "last_heartbeat_at": now,
            "status": "online",
            "last_error": False,
        })
        return access_token, refresh_token

    def action_generate_secret_key(self):
        for rec in self:
            rec.write({
                "secret_key": rec._new_secret_key(),
                "token_hash": False,
                "refresh_token_hash": False,
                "token_hint": False,
                "token_expires_at": False,
                "refresh_token_expires_at": False,
            })
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": _("Secret Key generated"), "message": _("A new secret key has been generated. Update the Controller configuration."), "type": "success", "sticky": False},
        }

    def action_block(self):
        self.write({"status": "blocked", "active": False, "token_hash": False, "refresh_token_hash": False, "last_error": _("Blocked by administrator.")})
        return True

    def action_unblock(self):
        self.write({"status": "offline", "active": True, "last_error": False})
        return True
