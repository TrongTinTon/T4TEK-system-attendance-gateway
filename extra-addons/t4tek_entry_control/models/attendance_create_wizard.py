from datetime import date
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
        Log = self.env["entry.control.attendance.log"].sudo()
        month_start = date(year, month, 1)
        if month == 12:
            next_month_start = date(year + 1, 1, 1)
        else:
            next_month_start = date(year, month + 1, 1)
        date_from = Log._local_day_bounds_utc(month_start)[0]
        date_to = Log._local_day_bounds_utc(next_month_start)[0]

        logs = Log.search([
            ("check_time", ">=", date_from),
            ("check_time", "<", date_to),
        ], order="check_time asc, id asc")

        # Do not recompute or overwrite raw log directions here.
        # The server already decided each log direction when it was ingested;
        # Create Attendances must only consume existing Check In / Check Out logs.
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
