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
        Log = self.env["entry.control.attendance.log"].sudo()
        # Search a broad UTC window. The actual month filter is applied inside
        # action_sync_hr_attendance by Device Local Day, not by raw UTC check_time.
        date_from, date_to = Log._broad_utc_search_bounds_for_local_days(date(year, month, 1), date(year, month, last_day))

        logs = Log.search([
            ("check_time", ">=", date_from),
            ("check_time", "<=", date_to),
        ], order="check_time asc, id asc")

        # Attendance Logs are the source of truth. This action first makes
        # Attendance Logs continuous by inserting system boundary logs when
        # needed, then derives hr.attendance from those logs.
        logs.with_context(
            entry_control_target_day_from=str(date(year, month, 1)),
            entry_control_target_day_to=str(date(year, month, last_day)),
        ).action_sync_hr_attendance()

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
