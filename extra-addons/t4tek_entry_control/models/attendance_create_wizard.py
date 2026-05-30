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
        end_date = date(year, month, last_day)

        total_logs_processed = 0

        # DUYỆT TỪNG NGÀY TRONG THÁNG
        current_date = start_date
        while current_date <= end_date:
            # Lấy range ngày theo module timezone, sau đó convert sang UTC-naive để query Odoo DB.
            local_start, local_end, db_start, db_end = LogModel._local_day_utc_bounds(current_date)
            next_date = current_date + timedelta(days=1)

            # 1. Tìm nhóm nhân viên quẹt thẻ dựa trên khoảng thời gian đã tịnh tiến
            attendance_groups = LogModel.read_group(
                domain=[
                    ("check_time", ">=", db_start),
                    ("check_time", "<", db_end),
                    ("employee_id", "!=", False),
                ],
                fields=["employee_id"],
                groupby=["employee_id"],
            )

            employee_ids = [g["employee_id"][0] for g in attendance_groups if g["employee_id"]]
            
            if employee_ids:
                for emp_id in employee_ids:
                    # Lấy logs thực tế của nhân viên nằm trong khoảng giờ đã dịch chuyển
                    emp_logs = LogModel.search([
                        ("employee_id", "=", emp_id),
                        ("check_time", ">=", db_start),
                        ("check_time", "<", db_end),
                    ], order="check_time asc, id asc")

                    if not emp_logs:
                        continue

                    total_logs_processed += len(emp_logs)

                    # 2. Xử lý bù ca đêm biên ngày
                    last_log = emp_logs[-1]
                    if last_log.direction == "in":
                        # Hàm này bên trong sẽ convert giờ module-local sang UTC-naive.
                        LogModel._find_or_create_system_log(
                            source_log=last_log,
                            direction="out",
                            local_dt=datetime.combine(current_date, time(23, 59, 59)),
                            reason=""
                        )
                        LogModel._find_or_create_system_log(
                            source_log=last_log,
                            direction="in",
                            local_dt=datetime.combine(next_date, time(0, 0, 0)),
                            reason=""
                        )
                        # Re-fetch lại tập hợp logs sau khi đã bù
                        emp_logs = LogModel.search([
                            ("employee_id", "=", emp_id),
                            ("check_time", ">=", db_start),
                            ("check_time", "<", db_end),
                        ], order="check_time asc, id asc")

                    # 3. Gộp logs thành 1 dòng duy nhất đại diện cho ngày đang xét
                    in_logs = emp_logs.filtered(lambda l: l.direction == "in")
                    out_logs = emp_logs.filtered(lambda l: l.direction == "out")

                    if in_logs and out_logs:
                        first_in_log = in_logs[0]
                        last_out_log = out_logs[-1]

                        if last_out_log.check_time > first_in_log.check_time:
                            existing_attendance = HrAttendance.search([
                                ("employee_id", "=", emp_id),
                                ("check_in", ">=", db_start),
                                ("check_in", "<", db_end),
                            ], limit=1)

                            try:
                                vals = {
                                    "employee_id": emp_id,
                                    "check_in": first_in_log.check_time,
                                    "check_out": last_out_log.check_time,
                                }
                                if existing_attendance:
                                    existing_attendance.write(vals)
                                    attendance_rec = existing_attendance
                                else:
                                    attendance_rec = HrAttendance.create(vals)
                                emp_logs.write({
                                    "hr_attendance_id": attendance_rec.id,
                                    "sync_status": "success",
                                    "error_message": False
                                })
                            except Exception as e:
                                emp_logs.write({"sync_status": "failed", "error_message": str(e)})

            current_date = next_date

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Create Attendances"),
                "message": _("Successfully processed data for %s/%s. Analyzed %s log entries.") % (month, year, total_logs_processed),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }