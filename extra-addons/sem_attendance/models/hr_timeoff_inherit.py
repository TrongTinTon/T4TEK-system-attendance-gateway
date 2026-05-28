from odoo import api, models, fields, _
from datetime import time
import logging


class HrTimeOff(models.Model):
    _name = 'hr.timeoff'
    _description = 'Xin nghỉ'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc'
    
   
    employee_id = fields.Many2one(
        'hr.employee',
        string='Nhân viên',
        required=True
    )

    holiday_id = fields.Many2one(
        'hr.holidays',
        string='Loại nghỉ',
        required=True
    )
    
    date_from = fields.Date(
        string='Ngày bắt đầu',
        required=True
    )
    
    date_to = fields.Date(
        string='Ngày kết thúc',
        required=True
    )
    
    time_from = fields.Float(
        string='Giờ bắt đầu',
        required=True
    )
    
    time_to = fields.Float(
        string='Giờ kết thúc',
        required=True
    )
    
    duration = fields.Float(
        string='Số giờ nghỉ',
        compute='_compute_duration',
        store=True
    )
    
    reason = fields.Text(
        string='Lý do',
        required=True
    )
    
    state = fields.Selection(
        [
            ('draft', 'Nháp'),
            ('submitted', 'Đã gửi'),
            ('approved', 'Đã duyệt'),
            ('rejected', 'Từ chối')
        ],
        string='Trạng thái',
        default='draft'
    )
    
    @api.depends('date_from', 'date_to', 'time_from', 'time_to')
    def _compute_duration(self):
        """Tính số giờ nghỉ"""
        for record in self:
            # Xử lý ca qua đêm
            if record.time_to < record.time_from:
                total_hours = (24 - record.time_from) + record.time_to
            else:
                total_hours = record.time_to - record.time_from
            
            record.duration = total_hours
    
    