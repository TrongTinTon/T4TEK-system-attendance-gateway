# -*- coding: utf-8 -*-
from odoo import models, fields, api, tools

class HrAttendanceReport(models.Model):
    _name = 'hr.attendance.report'
    _description = 'Attendance Monthly Report'
    _auto = False

    employee_id = fields.Many2one('hr.employee', string='Nhân viên', readonly=True)
    department_id = fields.Many2one('hr.department', string="Department", related="employee_id.department_id", readonly=True)
    month = fields.Char(string='Tháng', readonly=True)
    year = fields.Char(string='Năm', readonly=True)
    total_hours = fields.Float(string='Tổng giờ làm', readonly=True)
    total_days = fields.Integer(string='Tổng số ngày làm', readonly=True)
    total_duration = fields.Float(string='Tổng số công', readonly=True)
    total_overtime_hours = fields.Float(string='Tổng giờ tăng ca', readonly=True)
    total_late_minutes = fields.Integer(string='Tổng phút trễ', readonly=True)

    attendance_ids = fields.Many2many(
        'hr.attendance',
        compute='_compute_attendance_ids',
        string='Chi tiết chấm công'
    )

    def _compute_attendance_ids(self):
        for record in self:
            if record.employee_id and record.month and record.year:
                domain = [
                    ('employee_id', '=', record.employee_id.id),
                ]
                import calendar
                from datetime import date
                try:
                    year_int = int(record.year)
                    month_int = int(record.month)
                    start_date = date(year_int, month_int, 1)
                    end_date = date(year_int, month_int, calendar.monthrange(year_int, month_int)[1])
                    domain += [
                        ('check_in', '>=', start_date.strftime('%Y-%m-01 00:00:00')),
                        ('check_in', '<=', end_date.strftime('%Y-%m-%d 23:59:59'))
                    ]
                    record.attendance_ids = self.env['hr.attendance'].search(domain).ids
                except ValueError:
                    record.attendance_ids = False
            else:
                record.attendance_ids = False

    def init(self):
        # Drop table if it was previously created as a normal model, else drop view
        self.env.cr.execute("SELECT relkind FROM pg_class WHERE relname = %s", (self._table,))
        result = self.env.cr.fetchone()
        if result:
            if result[0] == 'r':  # ordinary table
                self.env.cr.execute('DROP TABLE "%s" CASCADE' % self._table)
            elif result[0] in ('v', 'm'):  # view or materialized view
                tools.drop_view_if_exists(self.env.cr, self._table)

        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    MIN(a.id) as id,
                    a.employee_id,
                    to_char(a.check_in AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Ho_Chi_Minh', 'MM') AS month,
                    to_char(a.check_in AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Ho_Chi_Minh', 'YYYY') AS year,
                    SUM(a.total_hours) AS total_hours,
                    COUNT(DISTINCT DATE(a.check_in AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Ho_Chi_Minh')) AS total_days,
                    SUM(a.duration_attendance) AS total_duration,
                    SUM(a.overtime_hours) AS total_overtime_hours,
                    SUM(a.late_minutes) AS total_late_minutes
                FROM hr_attendance a
                WHERE a.check_in IS NOT NULL
                GROUP BY 
                    a.employee_id, 
                    to_char(a.check_in AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Ho_Chi_Minh', 'MM'), 
                    to_char(a.check_in AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Ho_Chi_Minh', 'YYYY')
            )
        """ % (self._table,))
