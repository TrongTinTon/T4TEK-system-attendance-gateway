from odoo import api, models, fields
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class HrAttendanceCalendar(models.Model):
    _name = 'hr.attendance.calendar'
    _description = 'Chấm công (Lịch)'
    _order = 'date_start desc'

    name = fields.Char(
        string='Tiêu đề',
        compute='_compute_name',
        store=True,
    )

    employee_id = fields.Many2one(
        'hr.employee',
        string='Nhân viên',
        required=True,
        default=lambda self: self.env.user.employee_id,
    )

    date_start = fields.Datetime(
        string='Giờ vào',
        required=True,
        default=fields.Datetime.now,
    )

    date_stop = fields.Datetime(
        string='Giờ ra',
        required=True,
        default=lambda self: fields.Datetime.now() + timedelta(hours=1),
    )

    note = fields.Text(
        string='Ghi chú',
    )

    total_hours = fields.Float(
        string='Tổng giờ',
        compute='_compute_total_hours',
        store=True,
    )

    company_id = fields.Many2one(
        'res.company',
        string='Công ty',
        related='employee_id.company_id',
        store=True,
    )

    department_id = fields.Many2one(
        'hr.department',
        string='Phòng ban',
        related='employee_id.department_id',
        store=True,
    )

    @api.depends('employee_id', 'date_start')
    def _compute_name(self):
        for record in self:
            if record.employee_id and record.date_start:
                date_str = record.date_start.strftime('%d/%m/%Y')
                record.name = f"{record.employee_id.name} - {date_str}"
            else:
                record.name = 'Chấm công mới'

    @api.depends('date_start', 'date_stop')
    def _compute_total_hours(self):
        for record in self:
            if record.date_start and record.date_stop:
                delta = record.date_stop - record.date_start
                record.total_hours = delta.total_seconds() / 3600.0
            else:
                record.total_hours = 0.0
