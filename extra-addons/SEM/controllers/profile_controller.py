from odoo import http
from odoo.http import request
import base64

class ProfileController(http.Controller):

    @http.route('/sem/my_profile/data', type='json', auth='user')
    def my_profile_data(self, **kw):
        user = request.env.user
        emp = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        if not emp:
            return {'error': 'Tài khoản chưa được liên kết với hồ sơ nhân viên. Vui lòng liên hệ quản trị viên.'}

        return {
            # Header
            'name': emp.name or '',
            'job_title': emp.job_title or '',
            'image': emp.image_128 and emp.image_128.decode('utf-8') if isinstance(emp.image_128, bytes) else (emp.image_128 or ''),
            # Thông tin công việc (readonly)
            'code': emp.code or '',
            'department': emp.department_id.name if emp.department_id else '',
            'job': emp.job_id.name if emp.job_id else '',
            'manager': emp.manager_id.name if emp.manager_id else '',
            'parent': emp.parent_id.name if emp.parent_id else '',
            'coach': emp.coach_id.name if emp.coach_id else '',
            'work_location': emp.work_location_id.name if emp.work_location_id else '',
            'address': emp.address_id.display_name if emp.address_id else '',
            'probation_date': str(emp.probation_date) if emp.probation_date else '',
            'start_date': str(emp.start_date) if emp.start_date else '',
            'work_email': emp.work_email or '',
            'work_phone': emp.work_phone or '',
            'mobile_phone': emp.mobile_phone or '',
            # Chức năng & nhiệm vụ (readonly HTML)
            'onus': emp.onus or '',
            'missions': emp.missions or '',
            'job_description': emp.job_description or '',
            # Thông tin cá nhân (editable)
            'private_phone': emp.private_phone or '',
            'private_email': emp.private_email or '',
            'gender': emp.gender or '',
            'birthday': str(emp.birthday) if emp.birthday else '',
            'place_of_birth': emp.place_of_birth or '',
            'place_of_origin': emp.place_of_origin or '',
            'identification_id': emp.identification_id or '',
            'date_issuance_identity_card': str(emp.date_issuance_identity_card) if emp.date_issuance_identity_card else '',
            'local_issuance_identity_card': emp.local_issuance_identity_card or '',
            'marital': emp.marital or '',
            'children': emp.children or 0,
            'emergency_contact': emp.emergency_contact or '',
            'emergency_phone': emp.emergency_phone or '',
            # Địa chỉ thường trú
            'private_street': emp.private_street or '',
            'private_street2': emp.private_street2 or '',
            'private_state_id': emp.private_state_id.id if emp.private_state_id else False,
            'private_state_name': emp.private_state_id.name if emp.private_state_id else '',
            'private_state_ward_id': emp.private_state_ward.id if emp.private_state_ward else False,
            'private_state_ward_name': emp.private_state_ward.name if emp.private_state_ward else '',
            'private_country_id': emp.private_country_id.id if emp.private_country_id else False,
            'private_country_name': emp.private_country_id.name if emp.private_country_id else '',
            'private_zip': emp.private_zip or '',
            # Địa chỉ tạm trú
            'temp_street': emp.temp_street or '',
            'temp_street2': emp.temp_street2 or '',
            'temp_state_id': emp.temp_state_id.id if emp.temp_state_id else False,
            'temp_state_name': emp.temp_state_id.name if emp.temp_state_id else '',
            'temp_state_ward_id': emp.temp_state_ward.id if emp.temp_state_ward else False,
            'temp_state_ward_name': emp.temp_state_ward.name if emp.temp_state_ward else '',
            'temp_country_id': emp.temp_country_id.id if emp.temp_country_id else False,
            'temp_country_name': emp.temp_country_id.name if emp.temp_country_id else '',
            'temp_zip': emp.temp_zip or '',
            # Selection options
            'gender_options': [('male', 'Nam'), ('female', 'Nữ'), ('other', 'Khác')],
            'marital_options': [
                ('single', 'Độc thân'), ('married', 'Đã kết hôn'),
                ('cohabitant', 'Sống chung'), ('widower', 'Goá'), ('divorced', 'Ly hôn'),
            ],
        }

    @http.route('/sem/my_profile/get_states', type='json', auth='user')
    def get_states(self, country_id=False, **kw):
        domain = [('active', '=', True)]
        if country_id:
            domain.append(('country_id', '=', country_id))
        states = request.env['res.country.state'].sudo().search_read(domain, ['id', 'name'], order='name')
        return states

    @http.route('/sem/my_profile/get_wards', type='json', auth='user')
    def get_wards(self, state_id=False, **kw):
        if not state_id:
            return []
        wards = request.env['res.state.ward'].sudo().search_read(
            [('country_state_id', '=', state_id)], ['id', 'name'], order='name'
        )
        return wards

    @http.route('/sem/my_profile/save', type='json', auth='user')
    def my_profile_save(self, vals=None, **kw):
        if not vals:
            return {'success': False, 'error': 'Không có dữ liệu'}
        user = request.env.user
        emp = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        if not emp:
            return {'success': False, 'error': 'Không tìm thấy hồ sơ nhân viên'}

        allowed_fields = [
            'private_phone', 'private_email', 'gender', 'birthday',
            'place_of_birth', 'place_of_origin', 'identification_id',
            'date_issuance_identity_card', 'local_issuance_identity_card',
            'marital', 'children', 'emergency_contact', 'emergency_phone',
            'private_street', 'private_street2', 'private_state_id',
            'private_state_ward', 'private_country_id', 'private_zip',
            'temp_street', 'temp_street2', 'temp_state_id',
            'temp_state_ward', 'temp_country_id', 'temp_zip',
        ]
        write_vals = {k: v for k, v in vals.items() if k in allowed_fields}

        # Xử lý field Many2one: nếu None thì chuyển thành False
        many2one_fields = [
            'private_state_id', 'private_state_ward', 'private_country_id',
            'temp_state_id', 'temp_state_ward', 'temp_country_id',
        ]
        for f in many2one_fields:
            if f in write_vals and not write_vals[f]:
                write_vals[f] = False

        try:
            emp.write(write_vals)
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @http.route('/sem/my_profile/upload_avatar', type='http', auth='user', methods=['POST'], csrf=False)
    def upload_avatar(self, **kw):
        import json
        user = request.env.user
        emp = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        if not emp:
            return request.make_json_response({'success': False, 'error': 'Không tìm thấy hồ sơ'})

        file = kw.get('avatar')
        if not file:
            return request.make_json_response({'success': False, 'error': 'Không có file'})

        try:
            image_data = base64.b64encode(file.read())
            emp.write({'image_1920': image_data})
            image_b64 = emp.image_128.decode('utf-8') if isinstance(emp.image_128, bytes) else (emp.image_128 or '')
            return request.make_json_response({'success': True, 'image': image_b64})
        except Exception as e:
            return request.make_json_response({'success': False, 'error': str(e)})
