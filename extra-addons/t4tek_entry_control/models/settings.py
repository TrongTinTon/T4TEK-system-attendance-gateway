from zoneinfo import ZoneInfo

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class EntryControlSettings(models.TransientModel):
    _name = "entry.control.settings"
    _description = "Gatekeeper Settings"

    attendance_timezone = fields.Char(
        string="Module Timezone",
        required=True,
        default=lambda self: self._default_attendance_timezone(),
        help="Business timezone used by Gatekeeper for Attendance Logs, system-generated 23:59/00:00 logs, Create Attendances, and Cron.",
    )

    @api.model
    def _log_model(self):
        return self.env["entry.control.attendance.log"].sudo()

    @api.model
    def _default_attendance_timezone(self):
        return self._log_model()._attendance_timezone_name()

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "attendance_timezone" in fields_list:
            res["attendance_timezone"] = self._default_attendance_timezone()
        return res

    def _validate_timezone(self, tz_name):
        tz_name = str(tz_name or "").strip()
        if not tz_name:
            raise UserError(_("Module Timezone is required."))
        try:
            ZoneInfo(tz_name)
        except Exception:
            raise UserError(_("Invalid timezone '%s'. Please use an IANA timezone name, for example Asia/Ho_Chi_Minh.") % tz_name)
        return tz_name

    def _check_gatekeeper_admin(self):
        if not (self.env.user.has_group("t4tek_entry_control.group_entry_control_admin") or self.env.user.has_group("base.group_system")):
            raise UserError(_("Only Gatekeeper Administrators can change Gatekeeper Settings."))

    def action_save(self):
        self.ensure_one()
        self._check_gatekeeper_admin()
        tz_name = self._validate_timezone(self.attendance_timezone)
        Log = self._log_model()
        self.env["ir.config_parameter"].sudo().set_param(Log._CONFIG_ATTENDANCE_TIMEZONE, tz_name)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Gatekeeper Settings"),
                "message": _("Module timezone saved: %s") % tz_name,
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def action_reset_default(self):
        self.ensure_one()
        self._check_gatekeeper_admin()
        Log = self._log_model()
        tz_name = Log._DEFAULT_ATTENDANCE_TIMEZONE
        self.env["ir.config_parameter"].sudo().set_param(Log._CONFIG_ATTENDANCE_TIMEZONE, tz_name)
        self.attendance_timezone = tz_name
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Gatekeeper Settings"),
                "message": _("Module timezone reset to default: %s") % tz_name,
                "type": "success",
                "sticky": False,
            },
        }
