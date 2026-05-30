from datetime import date, datetime, time, timedelta
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
        HrAttendance = self.env["hr.attendance"].sudo()

        start_date = date(year, month, 1)
        month_end_date = date(year, month, last_day)

        # Manual creation follows the same business-day rule as the daily cron:
        # only completed module-local days are processed. This prevents the button
        # from creating a 23:59 system Check Out for the current open day.
        _now_utc, now_local = LogModel._module_now()
        module_today = now_local.date()
        last_completed_date = module_today - timedelta(days=1)
        end_date = min(month_end_date, last_completed_date)

        if end_date < start_date:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Create Attendances"),
                    "message": _("No completed business days to process for %s/%s in module timezone %s.") % (
                        month,
                        year,
                        LogModel._attendance_timezone_name(),
                    ),
                    "type": "warning",
                    "sticky": False,
                    "next": {"type": "ir.actions.act_window_close"},
                },
            }

        total_logs_processed = 0
        created_count = 0
        updated_count = 0
        failed_count = 0
        skipped_count = 0
        processed_days = 0

        # DUYỆT TỪNG NGÀY ĐÃ HOÀN TẤT TRONG THÁNG THEO MODULE TIMEZONE
        current_date = start_date
        while current_date <= end_date:
            processed_days += 1
            _local_start, _local_end, db_start, db_end = LogModel._local_day_utc_bounds(current_date)
            next_date = current_date + timedelta(days=1)

            attendance_groups = LogModel.read_group(
                domain=[
                    ("check_time", ">=", db_start),
                    ("check_time", "<", db_end),
                    ("employee_id", "!=", False),
                ],
                fields=["employee_id"],
                groupby=["employee_id"],
            )

            employee_ids = [g["employee_id"][0] for g in attendance_groups if g.get("employee_id")]

            for emp_id in employee_ids:
                emp_logs = LogModel.search([
                    ("employee_id", "=", emp_id),
                    ("check_time", ">=", db_start),
                    ("check_time", "<", db_end),
                ], order="check_time asc, id asc")

                if not emp_logs:
                    skipped_count += 1
                    continue

                total_logs_processed += len(emp_logs)

                last_log = emp_logs[-1]
                if last_log.direction == "in":
                    LogModel._find_or_create_system_log(
                        source_log=last_log,
                        direction="out",
                        local_dt=datetime.combine(current_date, time(23, 59, 59)),
                        reason="",
                    )
                    LogModel._find_or_create_system_log(
                        source_log=last_log,
                        direction="in",
                        local_dt=datetime.combine(next_date, time(0, 0, 0)),
                        reason="",
                    )
                    emp_logs = LogModel.search([
                        ("employee_id", "=", emp_id),
                        ("check_time", ">=", db_start),
                        ("check_time", "<", db_end),
                    ], order="check_time asc, id asc")

                in_logs = emp_logs.filtered(lambda l: l.direction == "in")
                out_logs = emp_logs.filtered(lambda l: l.direction == "out")

                if not in_logs or not out_logs:
                    skipped_count += 1
                    continue

                first_in_log = in_logs[0]
                last_out_log = out_logs[-1]

                if last_out_log.check_time <= first_in_log.check_time:
                    skipped_count += 1
                    continue

                existing_attendance = HrAttendance.search([
                    ("employee_id", "=", emp_id),
                    ("check_in", ">=", db_start),
                    ("check_in", "<", db_end),
                ], limit=1)

                vals = {
                    "employee_id": emp_id,
                    "check_in": first_in_log.check_time,
                    "check_out": last_out_log.check_time,
                }

                try:
                    if existing_attendance:
                        existing_attendance.write(vals)
                        attendance_rec = existing_attendance
                        updated_count += 1
                    else:
                        attendance_rec = HrAttendance.create(vals)
                        created_count += 1

                    emp_logs.write({
                        "hr_attendance_id": attendance_rec.id,
                        "sync_status": "success",
                        "error_message": False,
                    })
                except Exception as e:
                    failed_count += 1
                    emp_logs.write({"sync_status": "failed", "error_message": str(e)})

            current_date = next_date

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Create Attendances"),
                "message": _(
                    "Processed %s completed day(s) for %s/%s in timezone %s. Logs: %s. Created: %s. Updated: %s. Skipped: %s. Failed: %s."
                ) % (
                    processed_days,
                    month,
                    year,
                    LogModel._attendance_timezone_name(),
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
