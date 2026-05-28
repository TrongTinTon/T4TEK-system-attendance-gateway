from odoo import api, models, fields, _
from datetime import time
import logging

_logger = logging.getLogger(__name__)


class HRShift(models.Model):
    _name = 'hr.shift'
    _description = 'Ca làm việc'
    _order = 'sequence, start_time'
    
    # ===== THÔNG TIN CƠ BẢN =====
    name = fields.Char(
        string='Tên ca làm việc',
        required=True
    )
    
    code = fields.Char(
        string='Mã ca',
        required=True,
        unique=True
    )
    
    sequence = fields.Integer(
        string='Thứ tự',
        default=10
    )
    
    active = fields.Boolean(
        default=True
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Công ty',
        default=lambda self: self.env.company,
        required=True
    )
    
    # ===== THỜI GIAN =====
    start_time = fields.Float(
        string='Giờ bắt đầu',
        required=True,
        help='Giờ bắt đầu ca (0-24 hours)'
    )
    
    end_time = fields.Float(
        string='Giờ kết thúc',
        required=True,
        help='Giờ kết thúc ca (0-24 hours)'
    )
    
    break_duration = fields.Float(
        string='Thời gian nghỉ (giờ)',
        default=1.0
    )
    
    working_hours = fields.Float(
        string='Số giờ làm việc',
        compute='_compute_working_hours',
        store=True
    )
    
    # ===== CẤU HÌNH =====
    late_threshold = fields.Integer(
        string='Threshold đi trễ (phút)',
        default=5,
        help='Số phút trễ được coi là đi trễ'
    )
    
    early_leave_threshold = fields.Integer(
        string='Threshold về sớm (phút)',
        default=5,
        help='Số phút sớm được coi là về sớm'
    )
    
    color = fields.Integer(
        string='Màu sắc',
        default=0
    )
    
    # ===== NHÂN SỰ =====
    employee_ids = fields.Many2many(
        'hr.employee',
        'hr_shift_employee_rel',
        'shift_id',
        'employee_id',
        string='Nhân viên'
    )
    
    start_date = fields.Date(
        string='Ngày bắt đầu áp dụng',
        required=True,
        default=fields.Date.today
    )
    
    end_date = fields.Date(
        string='Ngày kết thúc áp dụng',
        help='Để trống nếu áp dụng vĩnh viễn'
    )
    
    # ===== MÔ TẢ =====
    description = fields.Text(
        string='Mô tả'
    )
    
    @api.depends('start_time', 'end_time', 'break_duration')
    def _compute_working_hours(self):
        """Tính số giờ làm việc thực tế"""
        for shift in self:
            # Xử lý ca qua đêm
            if shift.end_time < shift.start_time:
                # Ví dụ: 22:00 - 06:00
                total_hours = (24 - shift.start_time) + shift.end_time
            else:
                total_hours = shift.end_time - shift.start_time
            
            shift.working_hours = total_hours - shift.break_duration
    
    def _get_time_from_float(self, time_float):
        """Convert float (0-24) thành time object"""
        hours = int(time_float)
        minutes = int((time_float - hours) * 60)
        return time(hours, minutes)
    
    def name_get(self):
        """Hiển thị tên ca với thời gian"""
        result = []
        for shift in self:
            start_time_str = self._format_time(shift.start_time)
            end_time_str = self._format_time(shift.end_time)
            display_name = f"{shift.name} ({start_time_str} - {end_time_str})"
            result.append((shift.id, display_name))
        return result
    
    def _format_time(self, time_float):
        """Format thời gian float thành HH:MM"""
        hours = int(time_float)
        minutes = int((time_float - hours) * 60)
        return f"{hours:02d}:{minutes:02d}"
    
    @api.constrains('start_time', 'end_time')
    def _check_times(self):
        """Kiểm tra giờ hợp lệ"""
        for shift in self:
            if shift.start_time < 0 or shift.start_time > 24:
                raise ValueError(_('Giờ bắt đầu phải từ 0 đến 24'))
            if shift.end_time < 0 or shift.end_time > 24:
                raise ValueError(_('Giờ kết thúc phải từ 0 đến 24'))
