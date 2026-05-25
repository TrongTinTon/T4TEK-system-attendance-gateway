from odoo import models, fields, api, tools

class HREmployeeForecastReport(models.Model):
    _name = 'hr.employee.forecast.report'
    _description = 'Báo cáo Biến động nhân sự'
    _auto = False
    _order = 'date desc'

    employee_id = fields.Many2one('hr.employee', string='Nhân viên', readonly=True)
    date = fields.Date(string='Ngày', readonly=True)
    month = fields.Selection([
        ('01', 'Tháng 1'), ('02', 'Tháng 2'), ('03', 'Tháng 3'), ('04', 'Tháng 4'),
        ('05', 'Tháng 5'), ('06', 'Tháng 6'), ('07', 'Tháng 7'), ('08', 'Tháng 8'),
        ('09', 'Tháng 9'), ('10', 'Tháng 10'), ('11', 'Tháng 11'), ('12', 'Tháng 12')
    ], string='Tháng', readonly=True)
    year = fields.Char(string='Năm', readonly=True)
    week = fields.Char(string='Tuần', readonly=True)
    company_id = fields.Many2one('res.company', string='Công ty', readonly=True)
    department_id = fields.Many2one('hr.department', string='Phòng ban', readonly=True)
    job_id = fields.Many2one('hr.job', string='Chức danh', readonly=True)
    employee_count = fields.Float(string='Số lượng nhân viên', group_operator="sum", readonly=True, digits=(16, 0))
    employee_type = fields.Selection([
        ('official', 'Chính thức'),
        ('probation', 'Thử việc')
    ], string='Loại nhân viên', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    row_number() OVER () AS id,
                    e.id AS employee_id,
                    date_trunc('month', d.date)::date AS date,
                    to_char(d.date, 'MM') AS month,
                    to_char(d.date, 'YYYY') AS year,
                    to_char(d.date, 'WW') AS week,
                    e.company_id,
                    v.department_id,
                    v.job_id,
                    1 AS employee_count,
                    CASE 
                        WHEN v.contract_date_start IS NOT NULL AND date_trunc('month', d.date)::date >= date_trunc('month', v.contract_date_start)::date THEN 'official'
                        ELSE 'probation'
                    END AS employee_type
                FROM
                    hr_employee e
                LEFT JOIN hr_version v ON e.current_version_id = v.id
                CROSS JOIN LATERAL
                    generate_series(
                        date_trunc('month', LEAST(v.trial_date_end, v.contract_date_start))::date,
                        date_trunc('month', COALESCE(v.contract_date_end, (CURRENT_DATE + interval '1 year')))::date,
                        '1 month'::interval
                    ) AS d(date)
                WHERE
                    v.contract_date_start IS NOT NULL OR v.trial_date_end IS NOT NULL
            )
        """ % self._table)
