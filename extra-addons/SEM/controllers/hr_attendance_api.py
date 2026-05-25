import json
from odoo import http
from odoo.http import request


class HRAttendanceController(http.Controller):
    """
    Controller cho HR Attendance UI
    Cung cấp API endpoints để lấy dữ liệu từ hr.attendance
    """

    @http.route('/api/attendance/today', type='json', auth='user', methods=['GET'])
    def get_today_attendance(self, **kwargs):
        """Lấy danh sách chấm công hôm nay"""
        from datetime import date
        
        today = str(date.today())
        
        attendances = request.env['hr.attendance'].search([
            ('check_in', '>=', today + ' 00:00:00'),
            ('check_in', '<', today + ' 23:59:59')
        ])
        
        data = []
        for att in attendances:
            data.append({
                'id': att.id,
                'employee': att.employee_id.name,
                'employee_id': att.employee_id.id,
                'check_in': att.check_in,
                'check_out': att.check_out,
                'department': att.employee_id.department_id.name or '',
            })
        
        return {'status': 'success', 'data': data}

    @http.route('/api/attendance/month', type='json', auth='user', methods=['GET'])
    def get_month_attendance(self, year=None, month=None, **kwargs):
        """Lấy danh sách chấm công theo tháng"""
        from datetime import datetime
        
        if not year or not month:
            now = datetime.now()
            year, month = now.year, now.month
        
        start_date = f"{year}-{month:02d}-01"
        
        # Tính ngày cuối cùng của tháng
        if month == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{month + 1:02d}-01"
        
        attendances = request.env['hr.attendance'].search([
            ('check_in', '>=', start_date),
            ('check_in', '<', end_date)
        ], order='check_in desc')
        
        data = []
        for att in attendances:
            data.append({
                'id': att.id,
                'employee': att.employee_id.name,
                'employee_id': att.employee_id.id,
                'check_in': att.check_in,
                'check_out': att.check_out,
                'department': att.employee_id.department_id.name or '',
                'check_in_date': att.check_in.date() if att.check_in else None,
            })
        
        return {'status': 'success', 'data': data, 'year': year, 'month': month}

    @http.route('/api/attendance/employee/<int:employee_id>/month', type='json', auth='user', methods=['GET'])
    def get_employee_month_attendance(self, employee_id, year=None, month=None, **kwargs):
        """Lấy chấm công của một nhân viên trong tháng"""
        from datetime import datetime
        
        if not year or not month:
            now = datetime.now()
            year, month = now.year, now.month
        
        start_date = f"{year}-{month:02d}-01"
        
        if month == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{month + 1:02d}-01"
        
        attendances = request.env['hr.attendance'].search([
            ('employee_id', '=', employee_id),
            ('check_in', '>=', start_date),
            ('check_in', '<', end_date)
        ], order='check_in desc')
        
        data = []
        for att in attendances:
            check_in_time = att.check_in
            check_out_time = att.check_out
            total_hours = 0
            
            if check_in_time and check_out_time:
                delta = check_out_time - check_in_time
                total_hours = delta.total_seconds() / 3600
            
            data.append({
                'id': att.id,
                'check_in': att.check_in,
                'check_out': att.check_out,
                'total_hours': round(total_hours, 2),
                'check_in_date': att.check_in.date() if att.check_in else None,
            })
        
        return {'status': 'success', 'data': data, 'year': year, 'month': month}

    @http.route('/api/attendance/check-in', type='json', auth='user', methods=['POST'])
    def create_check_in(self, **kwargs):
        """Tạo check-in cho nhân viên hiện tại"""
        from datetime import datetime
        
        try:
            user = request.env.user
            employee = request.env['hr.employee'].search([('user_id', '=', user.id)], limit=1)
            
            if not employee:
                return {
                    'status': 'error',
                    'message': 'Không tìm thấy employee liên kết với user này'
                }
            
            note = kwargs.get('note', '')
            
            attendance = request.env['hr.attendance'].create({
                'employee_id': employee.id,
                'check_in': datetime.now(),
                'check_in_note': note,
            })
            
            return {
                'status': 'success',
                'message': 'Check-in thành công',
                'data': {
                    'id': attendance.id,
                    'employee': attendance.employee_id.name,
                    'check_in': str(attendance.check_in),
                }
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }

    @http.route('/api/attendance/<int:attendance_id>/check-out', type='json', auth='user', methods=['POST'])
    def create_check_out(self, attendance_id, **kwargs):
        """Tạo check-out cho record attendance"""
        from datetime import datetime
        
        try:
            attendance = request.env['hr.attendance'].browse(attendance_id)
            
            if not attendance:
                return {
                    'status': 'error',
                    'message': 'Không tìm thấy attendance record'
                }
            
            if attendance.check_out:
                return {
                    'status': 'error',
                    'message': 'Record này đã có check-out'
                }
            
            note = kwargs.get('note', '')
            
            attendance.write({
                'check_out': datetime.now(),
                'check_out_note': note,
            })
            
            return {
                'status': 'success',
                'message': 'Check-out thành công',
                'data': {
                    'id': attendance.id,
                    'employee': attendance.employee_id.name,
                    'check_out': str(attendance.check_out),
                }
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }

    @http.route('/api/attendance/stats', type='json', auth='user', methods=['GET'])
    def get_attendance_stats(self, **kwargs):
        """Lấy thống kê chấm công hôm nay"""
        from datetime import date
        
        today = str(date.today())
        
        attendances = request.env['hr.attendance'].search([
            ('check_in', '>=', today + ' 00:00:00'),
            ('check_in', '<', today + ' 23:59:59')
        ])
        
        all_employees = request.env['hr.employee'].search([('active', '=', True)])
        
        checked_in = len(attendances)
        checked_out = len([a for a in attendances if a.check_out])
        late = len([a for a in attendances if a.check_in.hour > 8 or 
                   (a.check_in.hour == 8 and a.check_in.minute > 5)])
        
        return {
            'status': 'success',
            'data': {
                'total_employees': len(all_employees),
                'checked_in': checked_in,
                'checked_out': checked_out,
                'late': late,
                'not_checked_in': len(all_employees) - checked_in,
            }
        }

    @http.route('/api/employees', type='json', auth='user', methods=['GET'])
    def get_employees(self, **kwargs):
        """Lấy danh sách nhân viên"""
        employees = request.env['hr.employee'].search([('active', '=', True)])
        
        data = []
        for emp in employees:
            data.append({
                'id': emp.id,
                'name': emp.name,
                'department': emp.department_id.name or '',
                'job': emp.job_id.name or '',
            })
        
        return {'status': 'success', 'data': data}
