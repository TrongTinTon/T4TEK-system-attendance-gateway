from odoo import http
from odoo.http import request
import json
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class HRAttendanceController(http.Controller):
    
    # ===== CHECK-IN/CHECK-OUT =====
    @http.route('/api/attendance/check-in', type='json', auth='user', methods=['POST'])
    def check_in(self, **kwargs):
        """API để nhân viên check-in"""
        try:
            employee = request.env['hr.employee'].search([
                ('user_id', '=', request.uid)
            ], limit=1)
            
            if not employee:
                return {
                    'success': False,
                    'message': 'Không tìm thấy hồ sơ nhân viên'
                }
            
            # Kiểm tra đã check-in hôm nay chưa
            today = datetime.now().date()
            existing = request.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                ('check_in', '>=', f'{today} 00:00:00'),
                ('check_in', '<=', f'{today} 23:59:59'),
                ('check_out', '=', False)
            ], limit=1)
            
            if existing:
                return {
                    'success': False,
                    'message': f'Bạn đã check-in lúc {existing.check_in.strftime("%H:%M:%S")}'
                }
            
            # Tạo bản ghi check-in
            attendance = request.env['hr.attendance'].create({
                'employee_id': employee.id,
                'check_in': datetime.now(),
                'location_checkin': kwargs.get('location'),
                'device_checkin': kwargs.get('device'),
                'check_in_note': kwargs.get('note')
            })
            
            return {
                'success': True,
                'message': f'Check-in thành công lúc {attendance.check_in.strftime("%H:%M:%S")}',
                'data': {
                    'id': attendance.id,
                    'check_in': attendance.check_in.isoformat(),
                    'employee': employee.name
                }
            }
        except Exception as e:
            _logger.error(f"Check-in error: {str(e)}")
            return {
                'success': False,
                'message': f'Lỗi: {str(e)}'
            }
    
    @http.route('/api/attendance/check-out', type='json', auth='user', methods=['POST'])
    def check_out(self, **kwargs):
        """API để nhân viên check-out"""
        try:
            employee = request.env['hr.employee'].search([
                ('user_id', '=', request.uid)
            ], limit=1)
            
            if not employee:
                return {
                    'success': False,
                    'message': 'Không tìm thấy hồ sơ nhân viên'
                }
            
            # Tìm bản ghi check-in hôm nay
            today = datetime.now().date()
            attendance = request.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                ('check_in', '>=', f'{today} 00:00:00'),
                ('check_in', '<=', f'{today} 23:59:59'),
                ('check_out', '=', False)
            ], limit=1)
            
            if not attendance:
                return {
                    'success': False,
                    'message': 'Bạn chưa check-in hôm nay'
                }
            
            # Cập nhật check-out
            attendance.write({
                'check_out': datetime.now(),
                'location_checkout': kwargs.get('location'),
                'device_checkout': kwargs.get('device'),
                'check_out_note': kwargs.get('note')
            })
            
            return {
                'success': True,
                'message': f'Check-out thành công lúc {attendance.check_out.strftime("%H:%M:%S")}',
                'data': {
                    'id': attendance.id,
                    'check_in': attendance.check_in.isoformat(),
                    'check_out': attendance.check_out.isoformat(),
                    'total_hours': attendance.total_hours,
                    'is_late': attendance.is_late,
                    'is_early_leave': attendance.is_early_leave
                }
            }
        except Exception as e:
            _logger.error(f"Check-out error: {str(e)}")
            return {
                'success': False,
                'message': f'Lỗi: {str(e)}'
            }
    
    # ===== GET ATTENDANCE STATUS =====
    @http.route('/api/attendance/status', type='json', auth='user', methods=['GET'])
    def get_status(self):
        """API lấy trạng thái chấm công hôm nay"""
        try:
            employee = request.env['hr.employee'].search([
                ('user_id', '=', request.uid)
            ], limit=1)
            
            if not employee:
                return {
                    'success': False,
                    'message': 'Không tìm thấy hồ sơ nhân viên'
                }
            
            today = datetime.now().date()
            attendance = request.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                ('check_in', '>=', f'{today} 00:00:00'),
                ('check_in', '<=', f'{today} 23:59:59')
            ], limit=1)
            
            if not attendance:
                return {
                    'success': True,
                    'data': {
                        'status': 'not_checked_in',
                        'message': 'Bạn chưa check-in hôm nay'
                    }
                }
            
            if not attendance.check_out:
                return {
                    'success': True,
                    'data': {
                        'status': 'checked_in',
                        'check_in': attendance.check_in.isoformat(),
                        'message': f'Đã check-in lúc {attendance.check_in.strftime("%H:%M:%S")}',
                        'elapsed_time': str(datetime.now() - attendance.check_in)
                    }
                }
            else:
                return {
                    'success': True,
                    'data': {
                        'status': 'checked_out',
                        'check_in': attendance.check_in.isoformat(),
                        'check_out': attendance.check_out.isoformat(),
                        'total_hours': attendance.total_hours,
                        'working_hours': attendance.working_hours,
                        'overtime_hours': attendance.overtime_hours,
                        'is_late': attendance.is_late,
                        'is_early_leave': attendance.is_early_leave,
                        'is_halfday': attendance.is_halfday,
                        'attendance_type': attendance.attendance_type
                    }
                }
        except Exception as e:
            _logger.error(f"Get status error: {str(e)}")
            return {
                'success': False,
                'message': f'Lỗi: {str(e)}'
            }
    
    # ===== GET ATTENDANCE HISTORY =====
    @http.route('/api/attendance/history', type='json', auth='user', methods=['GET'])
    def get_history(self, days=30):
        """API lấy lịch sử chấm công"""
        try:
            employee = request.env['hr.employee'].search([
                ('user_id', '=', request.uid)
            ], limit=1)
            
            if not employee:
                return {
                    'success': False,
                    'message': 'Không tìm thấy hồ sơ nhân viên'
                }
            
            # Lấy dữ liệu {days} ngày gần nhất
            from_date = (datetime.now() - timedelta(days=int(days))).date()
            
            reports = request.env['hr.attendance.report'].search([
                ('employee_id', '=', employee.id),
                ('date', '>=', from_date)
            ], order='date desc')
            
            data = []
            for report in reports:
                data.append({
                    'date': report.date.isoformat(),
                    'status': report.status,
                    'check_in': report.check_in.isoformat() if report.check_in else None,
                    'check_out': report.check_out.isoformat() if report.check_out else None,
                    'total_hours': report.total_hours,
                    'working_hours': report.working_hours,
                    'overtime_hours': report.overtime_hours,
                    'late_minutes': report.late_minutes,
                    'is_late': report.is_late,
                    'is_early_leave': report.is_early_leave,
                    'is_halfday': report.is_halfday,
                    'is_absent': report.is_absent
                })
            
            return {
                'success': True,
                'data': data
            }
        except Exception as e:
            _logger.error(f"Get history error: {str(e)}")
            return {
                'success': False,
                'message': f'Lỗi: {str(e)}'
            }
    
    # ===== ADMIN REPORT =====
    @http.route('/api/attendance/report/daily', type='json', auth='user', methods=['GET'])
    def get_daily_report(self, date=None, department_id=None):
        """API lấy báo cáo hàng ngày"""
        try:
            if not request.env.user.has_group('base.group_hr_manager'):
                return {
                    'success': False,
                    'message': 'Bạn không có quyền xem báo cáo'
                }
            
            if not date:
                date = datetime.now().date()
            else:
                date = datetime.strptime(date, '%Y-%m-%d').date()
            
            domain = [('date', '=', date)]
            if department_id:
                domain.append(('department_id', '=', int(department_id)))
            
            reports = request.env['hr.attendance.report'].search(domain)
            
            data = []
            for report in reports:
                data.append({
                    'id': report.id,
                    'employee': report.employee_id.name,
                    'department': report.department_id.name,
                    'status': report.status,
                    'check_in': report.check_in.strftime('%H:%M') if report.check_in else '-',
                    'check_out': report.check_out.strftime('%H:%M') if report.check_out else '-',
                    'total_hours': round(report.total_hours, 2),
                    'late_minutes': report.late_minutes
                })
            
            # Tính thống kê
            total = len(data)
            present = len([r for r in data if r['status'] == 'present'])
            absent = len([r for r in data if r['status'] == 'absent'])
            late = len([r for r in data if r['status'] == 'late'])
            early_leave = len([r for r in data if r['status'] == 'early_leave'])
            
            return {
                'success': True,
                'data': data,
                'statistics': {
                    'total': total,
                    'present': present,
                    'absent': absent,
                    'late': late,
                    'early_leave': early_leave
                }
            }
        except Exception as e:
            _logger.error(f"Get daily report error: {str(e)}")
            return {
                'success': False,
                'message': f'Lỗi: {str(e)}'
            }
    # ===== GET EMPLOYEES =====
    @http.route('/api/employees', type='json', auth='user', methods=['GET'])
    def get_employees(self):
        """API lấy danh sách nhân viên"""
        try:
            employees = request.env['hr.employee'].search([], limit=100)
            
            data = []
            for emp in employees:
                data.append({
                    'id': emp.id,
                    'name': emp.name,
                    'department_id': [emp.department_id.id, emp.department_id.name] if emp.department_id else None,
                    'job_id': [emp.job_id.id, emp.job_id.name] if emp.job_id else None,
                    'image_1920': emp.image_1920 if hasattr(emp, 'image_1920') else None,
                    'email': emp.work_email or '',
                    'phone': emp.mobile_phone or ''
                })
            
            return {
                'success': True,
                'records': data,
                'total_records': len(data)
            }
        except Exception as e:
            _logger.error(f"Get employees error: {str(e)}")
            return {
                'success': False,
                'records': [],
                'total_records': 0,
                'message': f'Lỗi: {str(e)}'
            }

    # ===== GET CURRENT EMPLOYEE =====
    @http.route('/api/employees/current', type='json', auth='user', methods=['GET'])
    def get_current_employee(self):
        """API lấy thông tin nhân viên hiện tại"""
        try:
            employee = request.env['hr.employee'].search([
                ('user_id', '=', request.uid)
            ], limit=1)
            
            if not employee:
                return {
                    'success': False,
                    'message': 'Không tìm thấy hồ sơ nhân viên'
                }
            
            return {
                'success': True,
                'record': {
                    'id': employee.id,
                    'name': employee.name,
                    'department_id': [employee.department_id.id, employee.department_id.name] if employee.department_id else None,
                    'job_id': [employee.job_id.id, employee.job_id.name] if employee.job_id else None,
                    'image_1920': employee.image_1920 if hasattr(employee, 'image_1920') else None,
                    'email': employee.work_email or '',
                    'phone': employee.mobile_phone or ''
                }
            }
        except Exception as e:
            _logger.error(f"Get current employee error: {str(e)}")
            return {
                'success': False,
                'message': f'Lỗi: {str(e)}'
            }

    # ===== GET SHIFTS =====
    @http.route('/api/shifts', type='json', auth='user', methods=['GET'])
    def get_shifts(self):
        """API lấy danh sách ca làm việc"""
        try:
            shifts = request.env['hr.shift'].search([], limit=100)
            
            data = []
            for shift in shifts:
                data.append({
                    'id': shift.id,
                    'name': shift.name,
                    'code': shift.code,
                    'start_time': shift.start_time,
                    'end_time': shift.end_time,
                    'working_hours': shift.working_hours,
                    'break_duration': shift.break_duration,
                    'late_threshold': shift.late_threshold,
                    'early_leave_threshold': shift.early_leave_threshold
                })
            
            return {
                'success': True,
                'records': data,
                'total_records': len(data)
            }
        except Exception as e:
            _logger.error(f"Get shifts error: {str(e)}")
            return {
                'success': False,
                'records': [],
                'total_records': 0,
                'message': f'Lỗi: {str(e)}'
            }