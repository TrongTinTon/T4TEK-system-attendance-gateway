from odoo import api, models, fields, _
from datetime import datetime, timedelta
import pytz
import logging

_logger = logging.getLogger(__name__)


class HRAttendanceInherit(models.Model):
    _name = 'hr.attendance'
    _inherit = ['hr.attendance', 'mail.thread', 'mail.activity.mixin']
    _description = 'Employee Attendance (Extended)'

    # Ghi đè lại 2 trường gốc của Odoo để bật tính năng tracking (lưu log chỉnh sửa)
    check_in = fields.Datetime(string="Check In", default=fields.Datetime.now, required=True, tracking=False)
    check_out = fields.Datetime(string="Check Out", tracking=False)
    validated_overtime_hours = fields.Float(string="Giờ tăng ca hợp lệ", compute='_compute_validated_overtime_hours', store=True, readonly=False, tracking=False)
    
    employee_code = fields.Char(
        string="Mã nhân viên",
        compute='_compute_employee_code',
        inverse='_inverse_employee_code',
        store=False,
        help='Mã nhân viên'
    )
    # ===== THÔNG TIN CHẤM CÔNG =====
    check_in_note = fields.Text(
        string='Ghi chú Check-in',
        help='Lý do, tình trạng khi check-in'
    )
    
    check_out_note = fields.Text(
        string='Ghi chú Check-out',
        help='Lý do, tình trạng khi check-out'
    )
    
    attendance_type = fields.Selection([
        ('normal', 'Bình thường'),
        ('late', 'Đi trễ'),
        ('early_leave', 'Về sớm'),
        ('late_and_early', 'Đi trễ & Về sớm'),
        ('absent', 'Vắng mặt'),
        ('holiday', 'Ngày lễ'),
        ('leave', 'Nghỉ phép'),
    ], string='Loại chấm công', default='normal', compute='_compute_attendance_type', store=True)
    
    # ===== TÍNH TOÁN THỜI GIAN =====
    total_hours = fields.Float(
        string='Tổng giờ làm việc',
        compute='_compute_total_hours',
        store=True
    )
    
    # base_working_days = fields.Float(
    #     string='Số công căn bản',
    #     compute='_compute_base_working_days',
    #     store=True
    # )
    
    overtime_hours = fields.Float(
        string='Giờ tăng ca',
        compute='_compute_overtime_hours',
        store=True
    )
    
    late_minutes = fields.Float(
        string='Thời gian trễ',
        compute='_compute_late_minutes',
        store=True
    )

    early_leave_minutes = fields.Float(
        string='Thời gian về sớm',
        compute='_compute_early_leave_minutes',
        store=True
    )
    
    # ===== TRẠNG THÁI =====
    is_late = fields.Boolean(
        string='Đi trễ?',
        compute='_compute_is_late',
        store=True
    )

    rsc_attendance_ids = fields.Many2many(
        'resource.calendar.attendance',
        string='Ca làm việc',
        compute='_compute_rsc_attendance',
        store=True
    )

    
    applied_calendar_id = fields.Many2one(
        'resource.calendar',
        string='Lịch làm việc áp dụng',
        store=True,
        readonly=False,
        help='Lịch làm việc đã được sử dụng để tính công thực tế ngay tại thời điểm nhân viên check-in/out.',
        copy=False
    )

    check_applied_calendar = fields.Boolean(
        string='Lịch cần cập nhật?',
        compute='_compute_check_applied_calendar',
    )

    is_early_leave = fields.Boolean(
        string='Về sớm?',
        compute='_compute_is_early_leave',
        store=True
    )
    
    is_halfday = fields.Boolean(
        string='Nửa ngày?',
        compute='_compute_is_halfday',
        store=True
    )
    
    is_absent = fields.Boolean(
        string='Vắng mặt?',
        compute='_compute_is_absent',
        store=True
    )
    
    # ===== PHÂN LOẠI =====
    # shift_id = fields.Many2one(
    #     'hr.shift',
    #     string='Ca làm việc',
    #     compute='_compute_shift_id',
    #     store=True
    # )
    
    location_checkin = fields.Char(
        string='Vị trí Check-in',
        help='GPS/vị trí khi check-in'
    )
    
    location_checkout = fields.Char(
        string='Vị trí Check-out',
        help='GPS/vị trí khi check-out'
    )
    
    device_checkin = fields.Char(
        string='Thiết bị Check-in',
        help='Thiết bị/máy chấm công khi check-in'
    )
    
    device_checkout = fields.Char(
        string='Thiết bị Check-out',
        help='Thiết bị/máy chấm công khi check-out'
    )
    
    # ===== CẤU HÌNH THEO QUY ĐỊNH =====
    # config_id removed

    # ===== QUY TRÌNH PHÒNG BAN =====
    department_id = fields.Many2one(
        'hr.department',
        related='employee_id.department_id',
        string='Phòng ban',
        store=True
    )
    
    manager_id = fields.Many2one(
        'hr.employee',
        related='employee_id.parent_id',
        string='Người quản lý trực tiếp',
        store=True
    )

    # ===== EMPLOYEE CODE (compute + inverse cho import) =====
    @api.depends('employee_id', 'employee_id.code')
    def _compute_employee_code(self):
        for rec in self:
            rec.employee_code = rec.employee_id.code or ''

    def _inverse_employee_code(self):
        """No-op: Chỉ cần inverse để Odoo cho phép field xuất hiện trong import wizard.
        Logic import thực tế được xử lý trong load()."""
        pass

    # ===== COMPUTATION METHODS =====
    @api.depends('check_in', 'check_out', 'is_late', 'is_early_leave')
    def _compute_attendance_type(self):
        """Xác định loại chấm công dựa trên thời gian"""
        for attendance in self:
            if not attendance.check_in:
                attendance.attendance_type = 'normal'
                continue

            # Kiểm tra ngày lễ hoặc nghỉ phép
            if attendance._is_holiday():
                attendance.attendance_type = 'holiday'
            elif attendance._is_on_leave():
                attendance.attendance_type = 'leave'
            elif not attendance.check_out:
                attendance.attendance_type = 'absent'
            elif attendance.is_late and attendance.is_early_leave:
                attendance.attendance_type = 'late_and_early'
            elif attendance.is_late:
                attendance.attendance_type = 'late'
            elif attendance.is_early_leave:
                attendance.attendance_type = 'early_leave'
            else:
                attendance.attendance_type = 'normal'
    
    @api.depends('check_in', 'check_out')
    def _compute_total_hours(self):
        """Tính tổng giờ làm việc (đã trừ giờ nghỉ mặc định)"""
        for attendance in self:
            if attendance.check_in and attendance.check_out:
                delta = attendance.check_out - attendance.check_in
                duration = delta.total_seconds() / 3600.0
                
                # Lấy giờ nghỉ mặc định (1h)
                break_time = 1.0
                
                # Trừ giờ nghỉ (đảm bảo không < 0)
                attendance.total_hours = max(0.0, duration - break_time)
            else:
                attendance.total_hours = 0.0
    
    # @api.depends('worked_hours', 'config_id.base_working_hours')
    # def _compute_base_working_days(self):
    #     """Tính số công căn bản dựa trên giờ làm thực tế so với giờ căn bản"""
    #     for attendance in self:
    #         standard = attendance.config_id.base_working_hours or 8.0
    #         if attendance.worked_hours >= standard:
    #             attendance.base_working_days = 1.0
    #         else:
    #             attendance.base_working_days = 0.0
    
    @api.depends('total_hours')
    def _compute_overtime_hours(self):
        """Tính giờ tăng ca (vượt quá giờ tiêu chuẩn)"""
        for attendance in self:
            standard = 8.0
            if attendance.total_hours > standard:
                attendance.overtime_hours = attendance.total_hours - standard
            else:
                attendance.overtime_hours = 0.0
    
    @api.depends('check_in', 'check_out', 'employee_id', 'applied_calendar_id')
    def _compute_rsc_attendance(self):
        for attendance in self:
            if not attendance.check_in:
                attendance.rsc_attendance_ids = False
                continue
            calendar = attendance.applied_calendar_id
            tz_name = calendar.tz or self.env.user.tz or 'UTC'
            if attendance.applied_calendar_id and attendance.applied_calendar_id.tz:
                tz_name = attendance.applied_calendar_id.tz
            elif attendance.employee_id and attendance.employee_id.tz:
                tz_name = attendance.employee_id.tz

            tz = pytz.timezone(tz_name)
            local_check_in = pytz.utc.localize(attendance.check_in).astimezone(tz)
            check_in_float = local_check_in.hour + local_check_in.minute / 60.0 + local_check_in.second / 3600.0

            if attendance.applied_calendar_id:
                dayofweek = str(local_check_in.weekday())
                shifts = attendance.applied_calendar_id.attendance_ids.filtered(lambda a: a.dayofweek == dayofweek)
                if shifts:
                    check_out_float = check_in_float
                    if attendance.check_out :
                        local_check_out = pytz.utc.localize(attendance.check_out).astimezone(tz)
                        check_out_float = local_check_out.hour + local_check_out.minute / 60.0 + local_check_out.second / 3600.0
                        
                        if check_out_float == check_in_float:
                            continue

                        overlapping_shifts = shifts.filtered(lambda s: s.hour_from < check_out_float and s.hour_to > check_in_float)
                    else:
                        overlapping_shifts = shifts.filtered(lambda s: s.hour_to > check_in_float)
                    
                    if overlapping_shifts:
                        attendance.rsc_attendance_ids = overlapping_shifts
                    else:
                        closest_shift = min(shifts, key=lambda s: abs(s.hour_from - check_in_float))
                        attendance.rsc_attendance_ids = closest_shift
                else:
                    attendance.rsc_attendance_ids = False
            else:
                attendance.rsc_attendance_ids = False
    @api.depends('check_in', 'employee_id', 'applied_calendar_id')
    def _compute_late_minutes(self):
        """Tính số phút đi trễ"""
        for attendance in self:
            if not attendance.check_in:
                attendance.late_minutes = 0
                continue
            calendar = attendance.applied_calendar_id
            tz_name = calendar.tz or self.env.user.tz or 'UTC'
            if attendance.applied_calendar_id and attendance.applied_calendar_id.tz:
                tz_name = attendance.applied_calendar_id.tz
            elif attendance.employee_id and attendance.employee_id.tz:
                tz_name = attendance.employee_id.tz
                
            tz = pytz.timezone(tz_name)
            local_check_in = pytz.utc.localize(attendance.check_in).astimezone(tz)
            check_in_float = local_check_in.hour + local_check_in.minute / 60.0 + local_check_in.second / 3600.0

            # Lấy giờ bắt đầu theo quy định từ ca làm việc (shift)
            expected_time_float = 0.0
            if attendance.applied_calendar_id:
                dayofweek = str(local_check_in.weekday())
                shifts = attendance.applied_calendar_id.attendance_ids.filtered(lambda a: a.dayofweek == dayofweek)
                if shifts:
                    # Chặn logic nếu check_out tồn tại để tìm khoảng làm việc thực sự
                    check_out_float = check_in_float
                    if attendance.check_out:
                        local_check_out = pytz.utc.localize(attendance.check_out).astimezone(tz)
                        check_out_float = local_check_out.hour + local_check_out.minute / 60.0 + local_check_out.second / 3600.0
                        
                        if check_out_float == check_in_float:
                            check_out_float += 0.01

                        # Lấy ca mà check-in/out đang nằm trong
                        overlapping_shifts = shifts.filtered(lambda s: s.hour_from < check_out_float and s.hour_to > check_in_float)
                    else:
                        # Nếu chưa checkout, lấy ca nào chưa kết thúc
                        overlapping_shifts = shifts.filtered(lambda s: s.hour_to > check_in_float)
                    
                    if overlapping_shifts:
                        # Nếu trùng với nhiều ca, thời gian bắt đầu trễ nhất nên là begin của ca đầu tiên
                        expected_time_float = min(overlapping_shifts.mapped('hour_from'))
                    else:
                        closest_shift = min(shifts, key=lambda s: abs(s.hour_from - check_in_float))
                        expected_time_float = closest_shift.hour_from
                else:
                    attendance.late_minutes = 0
                    continue
            else:
                attendance.late_minutes = 0
                continue
            
            if check_in_float > expected_time_float:
                attendance.late_minutes = round((check_in_float - expected_time_float), 4)
            else:
                attendance.late_minutes = 0.0
    
    @api.depends('late_minutes', 'applied_calendar_id')
    def _compute_is_late(self):
        """Xác định có đi trễ không (>= threshold)"""
        for attendance in self:
            company = attendance.employee_id.company_id or self.env.company
            # late_allow_time lưu phút, late_minutes lưu giờ → chuyển threshold sang giờ
            threshold_hours = (company.late_allow_time or 0) / 60.0

            attendance.is_late = attendance.late_minutes > 0 and attendance.late_minutes >= threshold_hours
    
    @api.depends('check_out', 'employee_id', 'applied_calendar_id')
    def _compute_is_early_leave(self):
        """Xác định có về sớm không"""
        for attendance in self:
            if not attendance.check_out:
                attendance.is_early_leave = False
                continue
            calendar = attendance.applied_calendar_id
            tz_name = calendar.tz or self.env.user.tz or 'UTC'
            if attendance.applied_calendar_id and attendance.applied_calendar_id.tz:
                tz_name = attendance.applied_calendar_id.tz
            elif attendance.employee_id and attendance.employee_id.tz:
                tz_name = attendance.employee_id.tz
                
            tz = pytz.timezone(tz_name)
            local_check_out = pytz.utc.localize(attendance.check_out).astimezone(tz)
            check_out_float = local_check_out.hour + local_check_out.minute / 60.0 + local_check_out.second / 3600.0

            # Lấy giờ kết thúc theo quy định (từ lịch)
            expected_time_float = 0.0
            if attendance.applied_calendar_id:
                dayofweek = str(local_check_out.weekday())
                shifts = attendance.applied_calendar_id.attendance_ids.filtered(lambda a: a.dayofweek == dayofweek)
                if shifts:
                    check_in_float = check_out_float
                    if attendance.check_in:
                        local_check_in = pytz.utc.localize(attendance.check_in).astimezone(tz)
                        check_in_float = local_check_in.hour + local_check_in.minute / 60.0 + local_check_in.second / 3600.0
                        
                        if check_out_float == check_in_float:
                            check_out_float += 0.01

                        overlapping_shifts = shifts.filtered(lambda s: s.hour_from < check_out_float and s.hour_to > check_in_float)
                    else:
                        overlapping_shifts = shifts.filtered(lambda s: s.hour_from < check_out_float)
                    
                    if overlapping_shifts:
                        # Nếu trùng nhiều ca, lấy ca cuối cùng kết thúc
                        expected_time_float = max(overlapping_shifts.mapped('hour_to'))
                    else:
                        closest_shift = min(shifts, key=lambda s: abs(s.hour_to - check_out_float))
                        expected_time_float = closest_shift.hour_to
                else:
                    attendance.is_early_leave = False
                    continue
            else:
                attendance.is_early_leave = False
                continue
            
            attendance.is_early_leave = check_out_float < expected_time_float
    
    @api.depends('check_out', 'employee_id', 'applied_calendar_id')
    def _compute_early_leave_minutes(self):
        """Tính số phút về sớm"""
        for attendance in self:
            if not attendance.check_out:
                attendance.early_leave_minutes = 0
                continue
            calendar = attendance.applied_calendar_id
            tz_name = calendar.tz or self.env.user.tz or 'UTC'
            if attendance.applied_calendar_id and attendance.applied_calendar_id.tz:
                tz_name = attendance.applied_calendar_id.tz
            elif attendance.employee_id and attendance.employee_id.tz:
                tz_name = attendance.employee_id.tz
                
            tz = pytz.timezone(tz_name)
            local_check_out = pytz.utc.localize(attendance.check_out).astimezone(tz)
            check_out_float = local_check_out.hour + local_check_out.minute / 60.0 + local_check_out.second / 3600.0

            # Lấy giờ kết thúc theo quy định (từ lịch)
            expected_time_float = 0.0
            if attendance.applied_calendar_id:
                dayofweek = str(local_check_out.weekday())
                shifts = attendance.applied_calendar_id.attendance_ids.filtered(lambda a: a.dayofweek == dayofweek)
                if shifts:
                    check_in_float = check_out_float
                    if attendance.check_in:
                        local_check_in = pytz.utc.localize(attendance.check_in).astimezone(tz)
                        check_in_float = local_check_in.hour + local_check_in.minute / 60.0 + local_check_in.second / 3600.0
                        
                        if check_out_float == check_in_float:
                            check_out_float += 0.01

                        overlapping_shifts = shifts.filtered(lambda s: s.hour_from < check_out_float and s.hour_to > check_in_float)
                    else:
                        overlapping_shifts = shifts.filtered(lambda s: s.hour_from < check_out_float)
                    
                    if overlapping_shifts:
                        # Nếu trùng nhiều ca, lấy ca cuối cùng kết thúc
                        expected_time_float = max(overlapping_shifts.mapped('hour_to'))
                    else:
                        closest_shift = min(shifts, key=lambda s: abs(s.hour_to - check_out_float))
                        expected_time_float = closest_shift.hour_to
                else:
                    attendance.early_leave_minutes = 0
                    continue
            else:
                attendance.early_leave_minutes = 0
                continue
            
            if check_out_float < expected_time_float:
                attendance.early_leave_minutes = int(round((expected_time_float - check_out_float) * 60))
            else:
                attendance.early_leave_minutes = 0
                

    @api.depends('is_late', 'is_early_leave', 'total_hours')
    def _compute_is_halfday(self):
        """Xác định có phải nửa ngày không"""
        for attendance in self:
            # Nửa ngày: làm < 4 giờ hoặc (đi trễ AND về sớm)
            attendance.is_halfday = (
                attendance.total_hours < 4 or
                (attendance.is_late and attendance.is_early_leave)
            )
    
    @api.depends('check_in', 'check_out')
    def _compute_is_absent(self):
        """Xác định có vắng mặt không"""
        for attendance in self:
            # Vắng mặt: không check-out hoặc làm < 3 giờ
            attendance.is_absent = (
                not attendance.check_out or
                attendance.total_hours < 3
            )
    
    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        """Khi chọn nhân viên trên giao diện, tự động điền lịch làm việc hiện tại của họ"""
        if self.employee_id:
            self.applied_calendar_id = self.employee_id.resource_calendar_id

    @api.depends('check_in', 'check_out', 'employee_id')
    def _compute_duration_attendance(self):
        # Đã chuyển logic sang module t4_hr_attendance_policy để lấy số công từ hr_work_entry
        pass
    
  
    
    #@api.depends('check_in', 'employee_id', 'employee_id.resource_calendar_id')
    # def _compute_duration_days(self):
    #     """
    #     Lấy số công (duration_days) trực tiếp từ resource.calendar.attendance
    #     của nhân viên dựa trên ngày check_in.
    #     """
    #     for attendance in self:
    #         if not attendance.check_in or not attendance.employee_id:
    #             attendance.duration_days = 0.0
    #             continue
            
    #         calendar = attendance.employee_id.resource_calendar_id
    #         if not calendar:
    #             attendance.duration_days = 0.0
    #             continue

    #         # Chuyển check_in về múi giờ của nhân viên/lịch để lấy đúng thứ trong tuần
    #         tz_name = calendar.tz or self.env.user.tz or 'UTC'
    #         tz = pytz.timezone(tz_name)
    #         local_check_in = pytz.utc.localize(attendance.check_in).astimezone(tz)
            
    #         # Day of week (0-6, Odoo convention: 0 is Monday)
    #         dayofweek = str(local_check_in.weekday())
            
    #         # Lấy tất cả attendance của ngày đó trong lịch
    #         attendances = calendar.attendance_ids.filtered(lambda a: a.dayofweek == dayofweek and not a.date_from and not a.date_to)
            
    #         # Tổng hợp duration_days (Trường công)
    #         if attendances:
    #             attendance.duration_days = sum(attendances.mapped('duration_days'))
    #         else:
    #             attendance.duration_days = 0.0

    # ===== HELPER METHODS =====
    def _is_holiday(self):
        """Kiểm tra ngày này có phải ngày lễ không"""
        self.ensure_one()
        if not self.check_in:
            return False
        # Kiểm tra xem Model có tồn tại không để tránh lỗi KeyError
        if 'hr.holidays.public' in self.env:
            holidays = self.env['hr.holidays.public'].search([
                ('date', '=', self.check_in.date())
            ])
            return bool(holidays)
        
        # Nếu không có hr.holidays.public, kiểm tra trong resource.calendar.leaves
        leaves = self.env['resource.calendar.leaves'].search([
            ('date_from', '<=', self.check_in),
            ('date_to', '>=', self.check_in),
            ('resource_id', '=', False)
        ])
        return bool(leaves)
    
    def _is_on_leave(self):
        """Kiểm tra nhân viên có đang nghỉ phép ngày này không"""
        self.ensure_one()
        leave = self.env['hr.leave'].search([
            ('employee_id', '=', self.employee_id.id),
            ('date_from', '<=', self.check_in),
            ('date_to', '>=', self.check_in),
            ('state', 'in', ['validate1', 'validate'])
        ])
        return bool(leave)
    
    @api.model
    def load(self, fields, data):
        """
        Override load (import Excel) để:
        1. Fix lỗi floating point precision của Excel
           (openpyxl đọc 17:30:00 thành 17:29:59.995 → Odoo nhận "17:29:59")
        2. Hỗ trợ import cột 'employee_code' (Mã nhân viên)
        """
        # --- Fix Excel floating point: làm tròn giây 55-59 lên phút kế tiếp ---
        datetime_fields = ['check_in', 'check_out']
        dt_indices = [fields.index(f) for f in datetime_fields if f in fields]

        if dt_indices:
            data = [list(row) for row in data]
            for row_num, row in enumerate(data):
                for idx in dt_indices:
                    val = row[idx]
                    if not val:
                        continue

                    dt = None
                    if isinstance(val, str):
                        val_str = val.strip()
                        formats_to_try = [
                            '%Y-%m-%d %H:%M:%S',
                            '%Y/%m/%d %H:%M:%S',
                            '%Y-%m-%d %I:%M:%S %p',
                            '%Y/%m/%d %I:%M:%S %p'
                        ]
                        for fmt in formats_to_try:
                            try:
                                dt = datetime.strptime(val_str, fmt)
                                break
                            except ValueError:
                                continue
                    elif isinstance(val, datetime):
                        dt = val

                    if dt and (dt.second >= 55 or dt.microsecond > 0):
                        _logger.info(
                            "Import fix precision row %d: %s → giây=%d, microsecond=%d",
                            row_num + 1, val, dt.second, dt.microsecond
                        )
                        # Làm tròn lên phút kế tiếp
                        if dt.second >= 55 or (dt.second >= 50 and dt.microsecond > 0):
                            dt = (dt + timedelta(seconds=(60 - dt.second))).replace(second=0, microsecond=0)
                        else:
                            dt = dt.replace(second=0, microsecond=0)
                        row[idx] = dt.strftime('%Y-%m-%d %H:%M:%S')
                        _logger.info("Import fix precision row %d: → fixed to %s", row_num + 1, row[idx])

        # --- Xử lý cột employee_code ---
        if 'employee_code' in fields:
            code_idx = fields.index('employee_code')

            if 'employee_id' not in fields:
                fields.append('employee_id')
                emp_id_idx = len(fields) - 1
                if not dt_indices:
                    data = [list(row) + [''] for row in data]
                else:
                    data = [row + [''] for row in data]
            else:
                emp_id_idx = fields.index('employee_id')
                if not dt_indices:
                    data = [list(row) for row in data]

            HrEmployee = self.env['hr.employee'].sudo()
            for row in data:
                code_val = row[code_idx]
                if code_val and (not row[emp_id_idx]):
                    employee = HrEmployee.search([('code', '=', str(code_val).strip())], limit=1)
                    if employee:
                        row[emp_id_idx] = employee.name

            # Xóa cột employee_code vì không ghi trực tiếp được
            fields = [f for i, f in enumerate(fields) if i != code_idx]
            data = [[val for i, val in enumerate(row) if i != code_idx] for row in data]

        return super().load(fields, data)

    @api.model
    def create(self, vals):
        """Override create để log và sync attendance.report"""
        # Chốt cứng lịch làm việc khi tạo mới (trường hợp tạo từ máy chấm công / API)
        if 'employee_id' in vals and not vals.get('applied_calendar_id'):
            employee = self.env['hr.employee'].browse(vals['employee_id'])
            if employee.resource_calendar_id:
                vals['applied_calendar_id'] = employee.resource_calendar_id.id

        record = super().create(vals)
       
        if not self._context.get('skip_status_change_message'):
            record._post_status_change_message()
       
        return record

    def write(self, vals):
        """Override write để log thay đổi và sync attendance.report"""
        # Chốt lại lịch nếu có sự thay đổi nhân viên thông qua code/API
        if 'employee_id' in vals and not vals.get('applied_calendar_id'):
            employee = self.env['hr.employee'].browse(vals['employee_id'])
            if employee.resource_calendar_id:
                vals['applied_calendar_id'] = employee.resource_calendar_id.id
                
        result = super().write(vals)
        significant_fields = ['check_in', 'check_out']
        if not self._context.get('skip_status_change_message'):
            if any(field in vals for field in significant_fields):
                self._post_status_change_message()
       
        return result

    
    # Xử lý cập nhập lại công theo lịch làm việc nếu bị thay đổi (Bỏ) - hiện tại xử lý bên work_entry
    # def action_update_applied_calendar(self):
    #     """Hành động nút bấm: Chủ động ép Lịch mới của nhân viên vào các bản ghi quá khứ hoặc sửa đổi công."""
    #     # Yêu cầu quyền user (Sẽ kiểm tra thêm ở View hoặc phương thức)
    #     if not self.env.user.has_group('sem_attendance.group_attendance_calendar_updater'):
    #         pass # Thường thì nếu View ẩn đi rồi cũng khá an toàn, nhưng kiểm tra luôn cho chắc.

    #     # Sử dụng context skip_status_change_message=True để tránh việc gán field kích hoạt log lẻ tẻ
    #     for attendance in self.with_context(skip_status_change_message=True):
    #         if not attendance.employee_id:
    #             continue
                
    #         old_calendar = attendance.applied_calendar_id
    #         new_calendar = attendance.employee_id.resource_calendar_id
    #         if old_calendar == new_calendar:
    #             pass # Bỏ early return để nút bấm có thể kích hoạt tính toán lại khi test
    #         # Ghi nhận lịch mới
    #         attendance.applied_calendar_id = new_calendar
            
    #         # Vô tình _compute_duration_attendance không tự chạy nếu chỉ đổi applied_calendar_id 
    #         # (Vì không đưa applied_calendar_id vào @api.depends để tránh auto).
    #         # Do đó chúng ta kích hoạt cưỡng ép việc tính toán (Re-evaluate):
    #         attendance._compute_duration_attendance()
            
    #         # Gộp thông báo vào bảng chi tiết luôn cho gọn
    #         msg = f"<b>[Hệ điều hành Chấm công]</b> Đã cập nhật lịch làm việc từ <i>'{old_calendar.name if old_calendar else 'Trống'}'</i> sang <i>'{new_calendar.name if new_calendar else 'Trống'}'</i>.<br/>"
    #         msg += f"Số công tính lại là: <b>{attendance.duration_attendance}</b> công.<br/><hr/>"
            
    #         # Gọi trực tiếp ghi log 1 lần duy nhất kèm thông báo trên
    #         attendance._post_status_change_message(body_prefix=msg)
            
    #     return True


    def _post_status_change_message(self, body_prefix=''):
        """Post message when status changes"""
        for record in self:
            emp_name = record.employee_id.name or 'Không rõ'
            emp_code = record.employee_id.code or 'N/A'
            dept_name = record.employee_id.department_id.name or 'Không xác định'

            subject = f"Cập nhật chấm công: {emp_name} (Mã NV: {emp_code}) - Phòng ban: {dept_name}"
            
            write_from = ""
            calendar = record.applied_calendar_id or record.employee_id.resource_calendar_id
            
            tz_name = calendar.tz if calendar else (self.env.user.tz or 'UTC')
            tz = pytz.timezone(tz_name)
            
            def format_dt(dt):
                if not dt: return ""
                try:
                    local_dt = pytz.utc.localize(dt).astimezone(tz)
                except ValueError:
                    local_dt = dt.astimezone(tz)
                return local_dt.strftime('%d/%m/%Y %H:%M:%S')

            check_in_str = format_dt(record.check_in)
            check_out_str = format_dt(record.check_out)
            
            if calendar and record.check_in:
                try:
                    local_in = pytz.utc.localize(record.check_in).astimezone(tz)
                except ValueError:
                    local_in = record.check_in.astimezone(tz)
                day_str = str(local_in.weekday())
                
                shifts = calendar.attendance_ids.filtered(lambda a: a.dayofweek == day_str)
                if shifts:
                    def float_to_time(f):
                        try:
                            f = float(f)
                            h = int(f)
                            m = int(round((f - h) * 60))
                            return f"{h:02d}:{m:02d}"
                        except (ValueError, TypeError):
                            return str(f)
                    
                    day_in_str = str(local_in.weekday())
                    in_float = local_in.hour + local_in.minute / 60.0
                    
                    local_out = False
                    day_out_str = False
                    out_float = 0.0
                    if record.check_out:
                        try:
                            local_out = pytz.utc.localize(record.check_out).astimezone(tz)
                        except ValueError:
                            local_out = record.check_out.astimezone(tz)
                        day_out_str = str(local_out.weekday())
                        out_float = local_out.hour + local_out.minute / 60.0

                    shift_strs: list[str] = []
                    
                    def format_time_diff(diff_float):
                        h = int(diff_float)
                        m = int(round((diff_float - h) * 60))
                        parts = []
                        if h > 0: parts.append(f"{h} giờ")
                        if m > 0: parts.append(f"{m} phút")
                        return " ".join(parts) if parts else "0 phút"
                        
                    for s in shifts:
                        f_val = getattr(s, 'write_from', getattr(s, 'hour_from', 0.0))
                        t_val = getattr(s, 'write_to', getattr(s, 'hour_to', 0.0))
                      
                        s_name = s.name or 'Ca'
                        s_day = getattr(s, 'dayofweek', '')
                        
                        shift_time_str = f"{float_to_time(f_val)} - {float_to_time(t_val)}"
                        
                        if not local_out:
                            shift_strs.append(f"<b>{s_name}</b> ({shift_time_str}): Chưa kết thúc")  # type: ignore
                        company = record.employee_id.company_id or self.env.company
                        sys_late = company.late_allow_time / 60.0
                        sys_early = company.early_allow_time / 60.0
                            
                        t_val_adj = float(t_val)
                        if t_val_adj <= float(f_val):
                            t_val_adj += 24.0
                            
                        out_float_adj = float(out_float)
                        if local_in and local_out:
                            diff_days = (local_out.date() - local_in.date()).days
                            out_float_adj += diff_days * 24.0

                        # Nếu giờ làm hoàn toàn nằm ngoài ca thì bỏ qua không hiện
                        if out_float_adj <= float(f_val) or float(in_float) >= t_val_adj:
                            continue
                            
                        achieved = False
                        if float(in_float) <= float(f_val) + sys_late and out_float_adj >= t_val_adj - sys_early:
                            achieved = True
                            
                        if achieved:
                            note = "Đủ ca"
                            shift_strs.append(f"<b>{s_name}</b> ({shift_time_str}): {note}")  # type: ignore
                        else:
                            # In ra log rành mạch lý do tại sao không đủ ca (giờ thực tế vs giờ chuẩn)
                            missing = max(0.0, float(in_float) - float(f_val) - sys_late) + max(0.0, t_val_adj - sys_early - out_float_adj)
                            debug_info = f"[Vào: {float_to_time(in_float)} <= {float_to_time(float(f_val)+sys_late)}? | Ra: {float_to_time(out_float_adj)} >= {float_to_time(t_val_adj-sys_early)}?]"
                            note = f"Không khớp do không nằm gọn trong thời gian quy định {debug_info}"
                            shift_strs.append(f"<b>{s_name}</b> ({shift_time_str}): {note} (+0.0 công)")  # type: ignore
                    
                    if shift_strs:
                        write_from = "<br/>" + "<br/>".join(" - " + s for s in shift_strs)
                    else:
                        write_from = "Không khớp với lịch ca nào"

            # Lấy đúng tên field ghi chú (check_in_note / check_out_note là trường gốc của module này)
            note_in = getattr(record, 'check_in_note', getattr(record, 'note_in', ''))
            note_out = getattr(record, 'check_out_note', getattr(record, 'note_out', ''))

            if calendar:
                calendar_html = (
                    f"<a href='/web#id={calendar.id}&model=resource.calendar&view_type=form' "
                    f"target='_blank' class='o_mail_partner o-mail-Message-trackingNew me-1 fw-bold text-info'>{calendar.name}</a>"
                )
            else:
                calendar_html = record._convert_str("")

            body = (
                f"{body_prefix}"
                f"<p>Check in - Check out: "
                f"{record._convert_str(check_in_str)} - {record._convert_str(check_out_str)}</p>"
                f"<p>Lịch làm việc: "
                f"{calendar_html}</p>"
                f"<p> Giờ vào theo lịch - Giờ ra theo lịch: "
                f"{record._convert_str(write_from)}</p>"
                f"<p> Ghi chú vào: "
                f"{record._convert_str(note_in)}</p>"
                f"<p> Ghi chú ra: "
                f"{record._convert_str(note_out)}</p>"
            )
            record.message_post(subject=subject, body=body, body_is_html=True)
    
    def _convert_str(self, text):
        """Convert text to formatted HTML span"""
        if text:
            return (
                f"<span class='o_mail_partner o-mail-Message-trackingNew "
                f"me-1 fw-bold text-info'>{text}</span>"
            )
        return ""

    @api.depends('applied_calendar_id', 'employee_id.resource_calendar_id')
    def _compute_check_applied_calendar(self):
        """Kiểm tra xem applied_calendar_id có đúng với resource_calendar_id không"""
        for record in self:
            current = record.employee_id.resource_calendar_id
            if not current or current == record.applied_calendar_id:
                record.check_applied_calendar = False
            else:
                record.check_applied_calendar = True

    # ===== CRON: TỰ ĐỘNG FILL CHECK_OUT 17:30 =====
    @api.model
    def _cron_auto_fill_checkout(self):
        """
        Cron job chạy lúc 00:00 mỗi ngày.
        Tìm tất cả attendance có check_in trong ngày hôm đó nhưng không có check_out,
        tự động fill check_out = ngày check_in + 17:30 (local time).
        """
        # Lấy timezone của công ty
        tz_name = (
            self.env.company.resource_calendar_id.tz
            if self.env.company.resource_calendar_id
            else self.env.user.tz or 'Asia/Ho_Chi_Minh'
        )
        tz = pytz.timezone(tz_name)

        # Ngày hôm nay (local)
        now_utc = fields.Datetime.now()
        now_local = pytz.utc.localize(now_utc).astimezone(tz)
        today_local = now_local.date()

        # Tìm khoảng UTC của ngày hôm nay
        day_start_local = tz.localize(datetime.combine(today_local, datetime.min.time()))
        day_end_local = day_start_local + timedelta(days=1)
        day_start_utc = day_start_local.astimezone(pytz.utc).replace(tzinfo=None)
        day_end_utc = day_end_local.astimezone(pytz.utc).replace(tzinfo=None)

        # Tìm attendance chỉ có check_in mà không có check_out trong ngày
        attendances = self.sudo().search([
            ('check_in', '>=', day_start_utc),
            ('check_in', '<', day_end_utc),
            ('check_out', '=', False),
        ])

        if not attendances:
            _logger.info("Cron auto fill checkout: Không có attendance nào cần fill check_out.")
            return True

        filled_count = 0
        for attendance in attendances:
            try:
                # Lấy ngày check_in local
                check_in_utc = pytz.utc.localize(attendance.check_in)
                check_in_local = check_in_utc.astimezone(tz)
                check_in_date = check_in_local.date()

                # Tạo check_out = ngày check_in + 17:30 local time
                checkout_local = tz.localize(
                    datetime.combine(check_in_date, datetime.min.time().replace(hour=17, minute=30))
                )
                checkout_utc = checkout_local.astimezone(pytz.utc).replace(tzinfo=None)

                # Chỉ fill nếu check_out >= check_in (tránh trường hợp check_in sau 17:30)
                if checkout_utc >= attendance.check_in:
                    attendance.with_context(skip_status_change_message=True).write({
                        'check_out': checkout_utc,
                        'check_out_note': 'Tự động fill bởi hệ thống (không có check-out)',
                    })
                    filled_count += 1
                else:
                    _logger.info(
                        "Cron auto fill checkout: Bỏ qua attendance %s vì check_in (%s) sau 17:30.",
                        attendance.id, check_in_local,
                    )
            except Exception as e:
                _logger.error(
                    "Cron auto fill checkout: Lỗi xử lý attendance %s - %s",
                    attendance.id, str(e),
                )

        _logger.info("Cron auto fill checkout: Đã fill check_out cho %d attendance records.", filled_count)
        return True

    # ===== RE-CHECK CHẤM CÔNG THEO CONTRACT (VERSION) =====
    def action_recheck_attendance_by_version(self):
        """
        Kiểm tra lại chấm công theo contract (hr.version) để lấy:
        - attendance_policy_id (chính sách chấm công)
        - resource_calendar_id (lịch làm việc)
        và cập nhật applied_calendar_id tương ứng.
        
        Gọi từ nút bấm trên giao diện hoặc từ wizard Work Entry.
        """
        HrVersion = self.env['hr.version'].sudo()
        updated_count = 0

        for attendance in self:
            if not attendance.employee_id or not attendance.check_in:
                continue

            employee = attendance.employee_id.sudo()

            # Lấy timezone
            tz_name = (
                employee.company_id.resource_calendar_id.tz
                if employee.company_id and employee.company_id.resource_calendar_id
                else employee.tz or self.env.user.tz or 'Asia/Ho_Chi_Minh'
            )
            tz = pytz.timezone(tz_name)

            # Chuyển check_in sang local date
            check_in_utc = pytz.utc.localize(attendance.check_in)
            check_in_local = check_in_utc.astimezone(tz)
            target_date = check_in_local.date()

            # Tìm version (contract) đang active tại ngày check_in
            version = self.env['hr.version']
            if hasattr(employee, '_get_version'):
                version = employee._get_version(target_date)

            if not version:
                continue

            updates = {}

            # Lấy lịch làm việc từ version
            new_calendar = version.resource_calendar_id
            if new_calendar and new_calendar != attendance.applied_calendar_id:
                updates['applied_calendar_id'] = new_calendar.id

            if updates:
                attendance.with_context(skip_status_change_message=True).write(updates)
                updated_count += 1

        # Nếu module t4_hr_attendance_policy đã cài, sync lại policy fields
        if hasattr(self, '_sync_attendance_policy_fields'):
            try:
                self._sync_attendance_policy_fields()
            except Exception as e:
                _logger.warning(
                    "Recheck attendance by version: Không thể sync policy fields - %s",
                    str(e),
                )

        if updated_count:
            _logger.info(
                "Recheck attendance by version: Cập nhật %d attendance records.",
                updated_count,
            )

        return True

    @api.model
    def _recheck_attendances_for_period(self, date_from, date_to, employee_ids=None):
        """
        Re-check tất cả attendance trong khoảng thời gian theo contract/version.
        Được gọi khi chạy Work Entry wizard.
        
        :param date_from: fields.Date - ngày bắt đầu
        :param date_to: fields.Date - ngày kết thúc
        :param employee_ids: list of int - ID nhân viên cần check (None = tất cả)
        """
        tz_name = (
            self.env.company.resource_calendar_id.tz
            if self.env.company.resource_calendar_id
            else self.env.user.tz or 'Asia/Ho_Chi_Minh'
        )
        tz = pytz.timezone(tz_name)

        # Chuyển date range sang UTC
        date_from = fields.Date.to_date(date_from)
        date_to = fields.Date.to_date(date_to)
        utc_start = tz.localize(
            datetime.combine(date_from, datetime.min.time())
        ).astimezone(pytz.utc).replace(tzinfo=None)
        utc_end = tz.localize(
            datetime.combine(date_to, datetime.max.time())
        ).astimezone(pytz.utc).replace(tzinfo=None)

        domain = [
            ('check_in', '>=', utc_start),
            ('check_in', '<=', utc_end),
        ]
        if employee_ids:
            domain.append(('employee_id', 'in', employee_ids))

        attendances = self.sudo().search(domain)
        if attendances:
            attendances.action_recheck_attendance_by_version()

        _logger.info(
            "Recheck attendances for period %s - %s: Processed %d records.",
            date_from, date_to, len(attendances),
        )
        return attendances