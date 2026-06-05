from datetime import date, timedelta
from calendar import monthrange

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class EntryControlCreateAttendanceWizard(models.TransientModel):
    _name = "entry.control.create.attendance.wizard"
    _description = "Create Attendances from Gatekeeper Logs"

    @api.model
    def _default_business_today(self):
        try:
            return self.env["entry.control.attendance.log"].sudo()._module_now()[1].date()
        except Exception:
            return fields.Date.context_today(self)

    month = fields.Selection([
        ("1", "January"), ("2", "February"), ("3", "March"), ("4", "April"),
        ("5", "May"), ("6", "June"), ("7", "July"), ("8", "August"),
        ("9", "September"), ("10", "October"), ("11", "November"), ("12", "December"),
    ], string="Month", required=True, default=lambda self: str(self._default_business_today().month))
    year = fields.Integer(string="Year", required=True, default=lambda self: self._default_business_today().year)

    def action_create_attendances(self):
        self.ensure_one()
        if not (self.env.user.has_group("t4tek_entry_control.group_entry_control_manager") or self.env.user.has_group("base.group_system")):
            raise UserError(_("Only Gatekeeper Managers can create Odoo Attendances from Gatekeeper Logs."))

        month = int(self.month)
        year = int(self.year)
        last_day = monthrange(year, month)[1]

        LogModel = self.env["entry.control.attendance.log"].sudo()
        controllers = LogModel._attendance_controllers_to_process()

        start_date = date(year, month, 1)
        month_end_date = date(year, month, last_day)

        total_logs_processed = 0
        created_count = 0
        updated_count = 0
        failed_count = 0
        skipped_count = 0
        processed_days = 0
        processed_controllers = 0
        timezone_summary = []

        if not controllers:
            controllers = self.env["entry.control.controller"].sudo().browse()

        # Process each Controller independently because every Controller may have
        # a different business timezone and therefore a different completed day.
        for controller in controllers:
            _now_utc, now_local = LogModel._controller_now(controller)
            controller_today = now_local.date()
            last_completed_date = controller_today - timedelta(days=1)
            end_date = min(month_end_date, last_completed_date)
            if end_date < start_date:
                continue

            processed_controllers += 1
            timezone_summary.append("%s=%s" % (controller.display_name, LogModel._attendance_timezone_name(controller)))
            current_date = start_date
            while current_date <= end_date:
                metrics = LogModel._create_attendances_for_controller_day(controller, current_date)
                processed_days += 1
                total_logs_processed += int(metrics.get("log_count") or 0)
                created_count += int(metrics.get("created_count") or 0)
                updated_count += int(metrics.get("updated_count") or 0)
                failed_count += int(metrics.get("failed_count") or 0)
                skipped_count += int(metrics.get("skipped_count") or 0)
                current_date = current_date + timedelta(days=1)

        if processed_days == 0:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Create Attendances"),
                    "message": _("No completed business days to process for %s/%s by Controller Timezone.") % (month, year),
                    "type": "warning",
                    "sticky": False,
                    "next": {"type": "ir.actions.act_window_close"},
                },
            }

        tz_text = "; ".join(timezone_summary[:8])
        if len(timezone_summary) > 8:
            tz_text += "; ... +%s more" % (len(timezone_summary) - 8)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Create Attendances"),
                "message": _(
                    "Processed %s completed controller-day(s) for %s/%s. Controllers: %s. Timezones: %s. Logs: %s. Created: %s. Updated: %s. Skipped: %s. Failed: %s."
                ) % (
                    processed_days,
                    month,
                    year,
                    processed_controllers,
                    tz_text,
                    total_logs_processed,
                    created_count,
                    updated_count,
                    skipped_count,
                    failed_count,
                ),
                "type": "success" if failed_count == 0 else "warning",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
