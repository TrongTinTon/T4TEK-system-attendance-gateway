# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import base64
import io
from datetime import datetime, timedelta
import pytz
import logging

_logger = logging.getLogger(__name__)

try:
    import openpyxl
except ImportError:
    openpyxl = None


class ImportAttendanceLineWizard(models.TransientModel):
    _name = 'import.attendance.line.wizard'
    _description = 'Dòng dữ liệu nhập chấm công'

    wizard_id = fields.Many2one('import.attendance.wizard', string='Wizard', required=True, ondelete='cascade')
    row_number = fields.Integer(string='Dòng')
    employee_id = fields.Many2one('hr.employee', string='Nhân viên')
    employee_code = fields.Char(string='Mã nhân viên (gốc)', help='Lưu lại mã nếu không tìm thấy nhân viên')
    check_in = fields.Datetime(string='Đăng nhập', required=True)
    check_out = fields.Datetime(string='Đăng xuất')
    is_valid = fields.Boolean(string='Hợp lệ', default=False)
    error_message = fields.Char(string='Lỗi')

class ImportAttendanceWizard(models.TransientModel):
    _name = 'import.attendance.wizard'
    _description = 'Wizard Nhập dữ liệu Chấm công từ Excel'

    state = fields.Selection([
        ('upload', 'Tải file lên'),
        ('preview', 'Kiểm tra dữ liệu')
    ], string='Trạng thái', default='upload')

    file_data = fields.Binary(string='File Excel')
    file_name = fields.Char(string='Tên file')
    overwrite_overlap = fields.Boolean(
        string='Ghi đè nếu trùng lặp',
        default=False,
        help="Nếu chọn, hệ thống sẽ tự động ghi đè giờ check-in/out của chấm công cũ nếu bị trùng thời gian."
    )
    
    line_ids = fields.One2many('import.attendance.line.wizard', 'wizard_id', string='Dữ liệu xem trước')

    def action_load_file(self):
        self.ensure_one()
        if not openpyxl:
            raise UserError(_("Vui lòng cài đặt thư viện 'openpyxl' (pip install openpyxl)."))

        if not self.file_data:
            raise UserError(_("Vui lòng chọn file Excel để đọc dữ liệu."))

        # Xóa dữ liệu cũ nếu có (trường hợp upload lại file)
        self.line_ids.unlink()

        # Giải mã file từ base64
        file_content = base64.b64decode(self.file_data)
        file_io = io.BytesIO(file_content)

        try:
            wb = openpyxl.load_workbook(file_io, data_only=True)
            sheet = wb.active
        except Exception as e:
            raise UserError(_("Lỗi khi đọc file Excel: %s") % str(e))

        # Đọc Header (Dòng 1)
        headers = [str(cell.value).strip() if cell.value else '' for cell in sheet[1]]
        
        # Tìm index các cột cần thiết
        try:
            col_code = headers.index('Mã nhân viên')
            col_in = headers.index('Đăng nhập')
            col_out = headers.index('Đăng xuất')
        except ValueError as e:
            raise UserError(_("File Excel không đúng định dạng. Yêu cầu phải có đủ 3 cột: 'Mã nhân viên', 'Đăng nhập', 'Đăng xuất'."))

        HrEmployee = self.env['hr.employee'].sudo()

        user_tz_name = self.env.user.tz or 'Asia/Ho_Chi_Minh'
        user_tz = pytz.timezone(user_tz_name)

        def parse_and_fix_datetime(val):
            if not val:
                return False
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
                if not dt:
                    return False
            elif isinstance(val, datetime):
                dt = val
            else:
                return False

            # Fix precision của Excel
            if dt.second >= 55 or (dt.second >= 50 and dt.microsecond > 0):
                dt = (dt + timedelta(seconds=(60 - dt.second))).replace(second=0, microsecond=0)
            else:
                dt = dt.replace(second=0, microsecond=0)
            return dt

        def local_to_utc(dt):
            if not dt:
                return False
            local_dt = user_tz.localize(dt)
            utc_dt = local_dt.astimezone(pytz.utc).replace(tzinfo=None)
            return utc_dt

        lines_vals = []

        # Đọc dữ liệu từ dòng 2
        for row_idx, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            code_val = row[col_code]
            check_in_val = row[col_in]
            check_out_val = row[col_out]

            if not code_val or not check_in_val:
                continue  # Bỏ qua dòng trống

            code_str = str(code_val).strip()
            employee = HrEmployee.search([('code', '=', code_str)], limit=1)

            check_in_dt = parse_and_fix_datetime(check_in_val)
            check_out_dt = parse_and_fix_datetime(check_out_val)

            utc_check_in = local_to_utc(check_in_dt)
            utc_check_out = local_to_utc(check_out_dt)

            line_val = {
                'row_number': row_idx,
                'employee_code': code_str,
                'employee_id': employee.id if employee else False,
                'check_in': utc_check_in,
                'check_out': utc_check_out,
            }
            lines_vals.append((0, 0, line_val))

        if not lines_vals:
            raise UserError(_("Không tìm thấy dữ liệu hợp lệ trong file Excel."))

        self.write({
            'line_ids': lines_vals,
            'state': 'preview'
        })
        
        # Chạy logic kiểm tra lần đầu
        self.action_validate()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'import.attendance.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_validate(self):
        self.ensure_one()
        HrAttendance = self.env['hr.attendance'].sudo()

        for line in self.line_ids:
            line.is_valid = True
            line.error_message = False
            errors = []

            if not line.employee_id:
                errors.append("Không tìm thấy nhân viên có mã %s" % line.employee_code)
                line.is_valid = False
            if not line.check_in:
                errors.append("Thiếu giờ Đăng nhập")
                line.is_valid = False
            if line.check_in and line.check_out and line.check_out < line.check_in:
                errors.append("Giờ ra phải sau giờ vào")
                line.is_valid = False

            if line.is_valid and line.employee_id and line.check_in:
                # Kiểm tra trùng lặp với dữ liệu TRONG FILE hiện tại (các dòng trên)
                overlap_in_file = self.line_ids.filtered(
                    lambda l: l.id != line.id and l.employee_id.id == line.employee_id.id and l.is_valid and \
                              l.check_in and \
                              ((not line.check_out and not l.check_out and l.check_in.date() == line.check_in.date()) or \
                               (line.check_out and l.check_in < line.check_out and (not l.check_out or l.check_out > line.check_in)))
                )
                if overlap_in_file:
                    errors.append("Bị trùng thời gian với dòng %s trong file" % overlap_in_file[0].row_number)
                    line.is_valid = False

                # Kiểm tra trùng lặp với hệ thống
                if line.is_valid:
                    domain = [
                        ('employee_id', '=', line.employee_id.id),
                        ('check_in', '<', line.check_out if line.check_out else (line.check_in + timedelta(hours=12))),
                        ('check_out', '>', line.check_in)
                    ]
                    if not line.check_out:
                        domain = [
                            ('employee_id', '=', line.employee_id.id),
                            ('check_in', '>=', line.check_in.replace(hour=0, minute=0, second=0)),
                            ('check_in', '<=', line.check_in.replace(hour=23, minute=59, second=59))
                        ]

                    overlapping_attendances = HrAttendance.search(domain)
                    if overlapping_attendances and not self.overwrite_overlap:
                        errors.append("Trùng dữ liệu cũ (tick 'Ghi đè' để sửa lại)")
                        line.is_valid = False

            if not line.is_valid:
                line.error_message = " | ".join(errors)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'import.attendance.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_import(self):
        self.ensure_one()
        valid_lines = self.line_ids.filtered(lambda l: l.is_valid)
        
        if not valid_lines:
            raise UserError(_("Không có dòng dữ liệu nào hợp lệ để nhập."))

        HrAttendance = self.env['hr.attendance'].sudo()
        imported_count = 0
        updated_count = 0

        for line in valid_lines:
            # Xử lý ghi đè nếu cần
            if self.overwrite_overlap:
                domain = [
                    ('employee_id', '=', line.employee_id.id),
                    ('check_in', '<', line.check_out if line.check_out else (line.check_in + timedelta(hours=12))),
                    ('check_out', '>', line.check_in)
                ]
                if not line.check_out:
                    domain = [
                        ('employee_id', '=', line.employee_id.id),
                        ('check_in', '>=', line.check_in.replace(hour=0, minute=0, second=0)),
                        ('check_in', '<=', line.check_in.replace(hour=23, minute=59, second=59))
                    ]
                overlapping_attendances = HrAttendance.search(domain)
                if overlapping_attendances:
                    updated_count += len(overlapping_attendances)
                    overlapping_attendances.unlink()

            # Tạo bản ghi mới (bỏ qua rule policy để tránh bug tự động lùi giờ check_out của t4_payroll)
            vals = {
                'employee_id': line.employee_id.id,
                'check_in': line.check_in,
            }
            if line.check_out:
                vals['check_out'] = line.check_out

            HrAttendance.with_context(skip_status_change_message=True, skip_t4_attendance_policy=True).create(vals)
            imported_count += 1

        message = _("Đã nhập thành công %s bản ghi.") % imported_count
        if updated_count > 0:
            message += _("\nĐã ghi đè %s bản ghi bị trùng.") % updated_count

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Nhập dữ liệu thành công"),
                'message': message,
                'type': 'success',
                'sticky': False,
            }
        }
