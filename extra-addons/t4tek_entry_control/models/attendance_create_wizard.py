from datetime import date
from calendar import monthrange

from odoo import api, fields, models, _


class EntryControlCreateAttendanceWizard(models.TransientModel):
    _name = "entry.control.create.attendance.wizard"
    _description = "Create Attendances from Entry Control Logs"

    month = fields.Selection([
        ("1", "January"),
        ("2", "February"),
        ("3", "March"),
        ("4", "April"),
        ("5", "May"),
        ("6", "June"),
        ("7", "July"),
        ("8", "August"),
        ("9", "September"),
        ("10", "October"),
        ("11", "November"),
        ("12", "December"),
    ], string="Month", required=True, default=lambda self: str(fields.Date.context_today(self).month))
    year = fields.Integer(string="Year", required=True, default=lambda self: fields.Date.context_today(self).year)

    def action_create_attendances(self):
        self.ensure_one()
        month = int(self.month)
        year = int(self.year)
        last_day = monthrange(year, month)[1]
        date_from = date(year, month, 1).strftime("%Y-%m-%d 00:00:00")
        date_to = date(year, month, last_day).strftime("%Y-%m-%d 23:59:59")

        Log = self.env["entry.control.attendance.log"].sudo()
        logs = Log.search([
            ("check_time", ">=", date_from),
            ("check_time", "<=", date_to),
        ], order="check_time asc, id asc")

        logs.action_recompute_directions()
        logs.action_sync_hr_attendance()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Create Attendances"),
                "message": _("Processed %s attendance log(s).") % len(logs),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
