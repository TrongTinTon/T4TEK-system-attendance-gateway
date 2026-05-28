from odoo import models, fields


class HRAttendanceExtended(models.Model):
    """
    Extend HR Attendance Model
    Thêm các field bổ sung cho chấm công
    """
    _inherit = 'hr.attendance'

    check_in_note = fields.Text(
        string='Check-in Note',
        help='Ghi chú khi check-in'
    )
    
    check_out_note = fields.Text(
        string='Check-out Note',
        help='Ghi chú khi check-out'
    )
    
    check_in_location = fields.Char(
        string='Check-in Location',
        help='Vị trí check-in'
    )
    
    check_out_location = fields.Char(
        string='Check-out Location',
        help='Vị trí check-out'
    )
    
    is_late = fields.Boolean(
        string='Is Late',
        compute='_compute_is_late',
        store=True,
        help='Đi muộn không'
    )
    
    total_hours = fields.Float(
        string='Total Hours',
        compute='_compute_total_hours',
        store=True,
        help='Tổng số giờ làm việc'
    )
    
    work_date = fields.Date(
        string='Work Date',
        compute='_compute_work_date',
        store=True,
        help='Ngày làm việc'
    )
    
    approval_status = fields.Selection(
        [('draft', 'Draft'),
         ('submitted', 'Submitted'),
         ('approved', 'Approved'),
         ('rejected', 'Rejected')],
        string='Approval Status',
        default='draft',
        help='Trạng thái duyệt chấm công'
    )
    
    approved_by = fields.Many2one(
        'res.users',
        string='Approved By',
        readonly=True,
        help='Người duyệt'
    )
    
    approved_date = fields.Datetime(
        string='Approved Date',
        readonly=True,
        help='Ngày duyệt'
    )
    
    rejection_reason = fields.Text(
        string='Rejection Reason',
        help='Lý do từ chối'
    )
    
    extra_hours = fields.Float(
        string='Extra Hours',
        compute='_compute_extra_hours',
        store=True,
        help='Giờ tăng ca'
    )

    def _compute_is_late(self):
        """Tính toán xem nhân viên có đi muộn không"""
        for record in self:
            if record.check_in:
                # Coi như muộn nếu check-in sau 8h05
                is_late = record.check_in.hour > 8 or (
                    record.check_in.hour == 8 and record.check_in.minute > 5
                )
                record.is_late = is_late
            else:
                record.is_late = False

    def _compute_total_hours(self):
        """Tính tổng số giờ làm việc"""
        for record in self:
            if record.check_in and record.check_out:
                delta = record.check_out - record.check_in
                record.total_hours = delta.total_seconds() / 3600
            else:
                record.total_hours = 0

    def _compute_work_date(self):
        """Tính ngày làm việc từ check_in"""
        for record in self:
            if record.check_in:
                record.work_date = record.check_in.date()
            else:
                record.work_date = None

    def _compute_extra_hours(self):
        """Tính giờ tăng ca (nếu làm việc > 8 giờ)"""
        for record in self:
            if record.total_hours > 8:
                record.extra_hours = record.total_hours - 8
            else:
                record.extra_hours = 0

   