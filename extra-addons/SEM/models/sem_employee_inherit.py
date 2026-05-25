from odoo import api, models, tools, _, fields
import re
from lxml import etree
import logging
_logger = logging.getLogger(__name__)
from odoo.http import request
from odoo.exceptions import ValidationError, UserError
from datetime import date
from dateutil.relativedelta import relativedelta

class SEMEmployeeInherit(models.Model):
    _inherit = 'hr.employee'

    resume_line_ids = fields.One2many(
        related='version_id.resume_line_ids',
        readonly=False,
    )

    employee_skill_ids = fields.One2many(
        related='version_id.employee_skill_ids',
        readonly=False,
    )

    manager_id = fields.Many2one(
        'hr.employee',
        string='Quản lý phòng ban',
        compute='_compute_manager_id',
        store=True, )

    @api.depends('department_id')
    def _compute_manager_id(self):
        for rec in self:
            rec.manager_id = rec.department_id.manager_id

    # Field khai báo thêm thông tin nhân viên
    place_of_origin = fields.Char(string='Quê quán')
    people_id = fields.Many2one('people.category', string='Dân tộc')
    religion_id = fields.Many2one('religion.category', string='Tôn giáo')

    private_street = fields.Char(string='Số/Ngõ (Thường trú)')
    private_street2 = fields.Char(string='Đường (Thường trú)')
    private_city = fields.Char(string='Thành phố (Thường trú)')
    private_state_id = fields.Many2one('res.country.state', string='Tỉnh/Thành (Thường trú)')
    private_zip = fields.Char(string='Mã bưu chính (Thường trú)')
    private_state_ward = fields.Many2one('res.state.ward', string='Phường Xã (Thường trú)')

    # Địa chỉ tạm trú
    temp_street = fields.Char("Tạm trú - Số nhà")
    temp_street2 = fields.Char("Tạm trú - Đường 2")
    temp_city = fields.Char("Tạm trú - Thành phố")
    temp_state_ward = fields.Many2one('res.state.ward', string='Phường Xã')
    temp_state_id = fields.Many2one("res.country.state", string="Tạm trú - Tỉnh/Thành",
        domain="[('country_id', '=?', temp_country_id)]")
    temp_zip = fields.Char("Tạm trú - Mã bưu chính")
    
    permanent_address = fields.Char(string="Địa chỉ thường chú")
    temporary_address = fields.Char(string="Địa chỉ tạm trú")
    # Tính lương
    salary_type = fields.Selection([
        ('Monthly', 'Lương theo tháng'),
        ('Daily', 'Lương theo ngày'),
        ('Hourly', 'Lương theo giờ'),
    ], string='Loại lương', default='Monthly')
    # salary_basic = fields.Float(string='Lương cơ bản')
    # salary_allowance = fields.Float(string='Phụ cấp lương cơ bản')
    # salary_position = fields.Float(string='Phụ cấp chức vụ')
    

    @api.model
    def _default_country(self):
        country = self.env.company.country_id
        if not country:
            country = self.env['res.country'].search([('code', '=', 'VN')], limit=1)
        return country

    private_country_id = fields.Many2one(
        'res.country',
        default=lambda self: self._default_country()
    )

    temp_country_id = fields.Many2one(
        'res.country',
        string="Tạm trú - Quốc gia",
        default=lambda self: self._default_country()
    )


    probation_date = fields.Date(string='Ngày thử việc')
    probation_period = fields.Integer(string='Thời gian thử việc (Ngày)')

    start_date = fields.Date(string='Ngày chính thức')
    end_date = fields.Date(string='Ngày nghỉ việc')

    cultural_level_id = fields.Many2one('cultural.level.category', string='Trình độ văn hóa')
    date_issuance_identity_card = fields.Date(string='Ngày cấp CCCD')
    local_issuance_identity_card = fields.Char(string='Nơi cấp CCCD')

    
    code = fields.Char(string='Mã nhân viên', required=True)
    id_number = fields.Char(string='Số ID', required=True)
  
    _sql_constraints = [
    ('code_unique', 'UNIQUE(code)', 'Mã Nhân Viên đã tồn tại trong hệ thống.'),
    ('id_number_unique', 'UNIQUE(id_number)', 'Số ID đã tồn tại trong hệ thống.'),]

    parent_id = fields.Many2one(
        related='version_id.parent_id',
        readonly=False,
        string='Parent Employee',
        index=True
    )

    # Field mặc định, có fix lại
    work_email = fields.Char(string='Work Email', required=True)
    address_id = fields.Many2one(
        'res.partner',
        string='Khu vực',
    )
    allowed_address_ids = fields.Many2many(
        'res.partner',
        compute='_compute_allowed_address_ids',
        string='Allowed Addresses',
    )

    allowed_job_ids = fields.Many2many('hr.job', compute='_compute_allowed_job_ids')
    user_state = fields.Selection(related='user_id.state', string="User State", readonly=True)
    version_is_approved = fields.Boolean(related='version_id.is_approved', string='Version Approved', readonly=True)
    require_version_approval = fields.Boolean(
        string='Bắt buộc duyệt phiên bản',
        compute='_compute_require_version_approval'
    )

    def _compute_require_version_approval(self):
        for rec in self:
            company = rec.company_id or self.env.company
            rec.require_version_approval = company.require_version_approval

    @api.depends('department_id')
    def _compute_allowed_job_ids(self):
        for rec in self:
            if rec.department_id:
                rec.allowed_job_ids = rec.department_id.dept_job_ids.mapped('job_id')
            else:
                rec.allowed_job_ids = self.env['hr.job'].search([])

    @api.onchange('department_id')
    def _onchange_department_job_reset(self):
        if self.department_id and self.job_id:
            valid_jobs = self.department_id.dept_job_ids.mapped('job_id')
            if self.job_id not in valid_jobs:
                self.job_id = False

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        # Tự động gán readonly="version_is_approved" cho tất cả các field nằm trong notebook
        res = super().get_view(view_id=view_id, view_type=view_type, **options)
        if view_type == 'form':
            doc = etree.XML(res['arch'])
            
            # Đảm bảo field version_is_approved và require_version_approval luôn tồn tại trong view để không bị lỗi evaluate frontend
            if not doc.xpath("//field[@name='version_is_approved']"):
                for form in doc.xpath("//form"):
                    etree.SubElement(form, "field", name="version_is_approved", invisible="1")
            
            if not doc.xpath("//field[@name='require_version_approval']"):
                for form in doc.xpath("//form"):
                    etree.SubElement(form, "field", name="require_version_approval", invisible="1")
                # Tiêm metadata cho field vì OwlFE cần có định nghĩa trong models
                field_meta = self.fields_get(['version_is_approved']).get('version_is_approved')
                if field_meta:
                    if 'models' in res:
                        # Odoo frozendict iteration yields keys. Unfreeze safely using .items() if available or unpacking.
                        res_models_unfrozen = {k: v for k, v in res['models'].items()} if hasattr(res['models'], 'items') else dict(res['models'])
                        if self._name in res_models_unfrozen:
                            cm_data = res_models_unfrozen[self._name]
                            if hasattr(cm_data, 'items'):
                                cm_data_unfrozen = {k: v for k, v in cm_data.items()}
                                cm_data_unfrozen['version_is_approved'] = field_meta
                            else:
                                # Fallback if it's genuinely a list of strings
                                cm_data_unfrozen = list(cm_data)
                                if 'version_is_approved' not in cm_data_unfrozen:
                                    cm_data_unfrozen.append('version_is_approved')
                                    
                            res_models_unfrozen[self._name] = cm_data_unfrozen
                        res['models'] = res_models_unfrozen
                    elif 'fields' in res:
                        res_fields = {k: v for k, v in res['fields'].items()} if hasattr(res['fields'], 'items') else dict(res['fields'])
                        res_fields['version_is_approved'] = field_meta
                        res['fields'] = res_fields
                        
                req_meta = self.fields_get(['require_version_approval']).get('require_version_approval')
                if req_meta:
                    if 'models' in res:
                        res_models_unfrozen = {k: v for k, v in res['models'].items()} if hasattr(res['models'], 'items') else dict(res['models'])
                        if self._name in res_models_unfrozen:
                            cm_data = res_models_unfrozen[self._name]
                            if hasattr(cm_data, 'items'):
                                cm_data_unfrozen = {k: v for k, v in cm_data.items()}
                                cm_data_unfrozen['require_version_approval'] = req_meta
                            else:
                                cm_data_unfrozen = list(cm_data)
                                if 'require_version_approval' not in cm_data_unfrozen:
                                    cm_data_unfrozen.append('require_version_approval')
                            res_models_unfrozen[self._name] = cm_data_unfrozen
                        res['models'] = res_models_unfrozen
                    elif 'fields' in res:
                        res_fields = {k: v for k, v in res['fields'].items()} if hasattr(res['fields'], 'items') else dict(res['fields'])
                        res_fields['require_version_approval'] = req_meta
                        res['fields'] = res_fields
            
            # Gán trạng thái khóa cho các field
            # Chỉ áp dụng cho các field thuộc page mà KHÔNG nằm con một field khác (như list/tree bên trong field quan hệ)
            for node in doc.xpath("//notebook//page//field[not(ancestor::field)]"):
                if not node.get('readonly'):
                    node.set('readonly', 'version_is_approved and require_version_approval')
                    
            res['arch'] = etree.tostring(doc, encoding='unicode')
        return res

    @api.depends('company_id')
    def _compute_allowed_address_ids(self):
        for rec in self:
            company = rec.company_id or self.env.company
            company_partner = company.partner_id
            child_partners = company_partner.child_ids.filtered(
                lambda p: not p.ref_company_ids
            )
            rec.allowed_address_ids = company_partner | child_partners

    @api.onchange('company_id')
    def _onchange_company_id(self):
        self.address_id = False
        self.work_location_id = False

    @api.constrains('address_id', 'company_id')
    def _check_address_in_company(self):
        for rec in self:
            if rec.address_id:
                company = rec.company_id or self.env.company
                company_partner = company.partner_id
                child_partners = company_partner.child_ids.filtered(
                    lambda p: not p.ref_company_ids
                )
                allowed = company_partner | child_partners
                if rec.address_id not in allowed:
                    raise ValidationError(
                        _("Khu vực '%s' không thuộc danh sách khu vực của công ty '%s'. "
                          "Vui lòng chọn khu vực đã được khai báo trong Danh sách khu vực của công ty.")
                        % (rec.address_id.display_name, company.name)
                    )


    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)

        for employee in employees:
            # ------------------------------
            # 1. Tạo partner trước nếu chưa có
            # ------------------------------
            if not employee.work_contact_id:
                partner_vals = {
                    'name': employee.name or '',
                    'company_id': employee.company_id.id if employee.company_id else False,
                }
                if employee.work_email:
                    partner_vals['email'] = employee.work_email
                partner = self.env['res.partner'].create(partner_vals)
                employee.work_contact_id = partner

            # ------------------------------
            # 2. Tạo user nếu chưa có và có work_email
            # ------------------------------
            # if not employee.user_id and employee.work_email:
            #     employee.action_create_user()

        # ------------------------------
        # 3. Đồng bộ User vào Groups
        # ------------------------------
        # sync_emps = employees.filtered(lambda e: e.department_id or e.job_id or e.managed_dept_ids)
        # if sync_emps:
        #     self.env['hr.department'].sudo().add_User2Groups(sync_emps)

        return employees

    def action_create_user(self):
        """
        Tạo User cho nhân viên thông qua logic của CoreApp.
        """
        odoobot_id = self.env['res.users']._get_odoobot_id()
        for employee in self:
            if not employee.user_id and employee.work_email:
                user_vals = {
                    'login': employee.work_email,
                    'company_id': employee.company_id.id if employee.company_id else False,
                    'partner_id': employee.work_contact_id.id if employee.work_contact_id else False,
                    'is_from_CoreApp': True,
                }

                new_user = self.env['res.users'].with_user(odoobot_id).sudo().with_context(no_reset_password=True).create([user_vals])
                employee.user_id = new_user
        return True

    def action_send_invitation(self):
        """
        Gửi mail mời nhận việc / đặt mật khẩu (Kế thừa luồng CoreApp).
        """
        self.ensure_one()
        if not self.user_id:
            self.action_create_user()
        
        if self.user_id:
            return self.user_id.sudo().with_context(create_user=1).action_reset_password()
        return True

    def action_reset_password(self):
        """
        Gửi mail reset mật khẩu (khi user đã active).
        """
        self.ensure_one()
        if self.user_id:
            return self.user_id.sudo().action_reset_password()
        return True

    @api.model
    def get_attendance_data(self):
        """
        Securely returns employee data for the Attendance UI using sudo().
        """
        employees = self.sudo().search_read([], ["name", "job_id", "department_id", "barcode"])
        return employees

    def create_version(self, *args, **kwargs):
        # 1. Thêm validate: Không cho tạo version mới nếu version hiện tại chưa được duyệt
        records = self
        if not records and args:
            first_arg = args[0]
            if isinstance(first_arg, (int, list, tuple)):
                ids = [first_arg] if isinstance(first_arg, int) else first_arg
                if all(isinstance(i, int) for i in ids):
                    records = self.browse(ids)

        # 2. Truyền context bypass để hệ thống được phép update lại old_version (ví dụ set active=False hoặc gán ngày kết thúc)
        return super(SEMEmployeeInherit, self.with_context(bypass_approval_check=True)).create_version(*args, **kwargs)

    def action_approve_current_version(self):
        self.ensure_one()
        if not self.version_id:
            raise UserError(_("Không có phiên bản để duyệt."))
        self.version_id.action_approve()
        return {'type': 'ir.actions.client', 'tag': 'reload'}


    @api.model
    def get_internal_resume_lines(self, res_id, res_model):
        if not res_id:
            return []
        if res_model == 'res.users':
            res_id = self.env['res.users'].browse(res_id).employee_id.id
        if not self.env['hr.employee.public'].browse(res_id).has_access('read'):
            raise UserError(self.env._("You cannot access the resume of this employee."))
            
        res = []
        all_versions = self.env['hr.employee'].sudo().browse(res_id).version_ids
        if not all_versions:
            return res
            
        # Lọc version dựa trên context (để map đúng với lịch sử nhân viên)
        v_id = self.env.context.get('version_id')
        if v_id:
            if isinstance(v_id, (list, tuple)):
                v_id = v_id[0]
            elif isinstance(v_id, dict):
                v_id = v_id.get('id') or v_id.get('value')
                
            # Xử lý trường hợp Odoo truyền chuỗi virtual_id khi đang tạo Web (NewId)
            try:
                numeric_v_id = int(v_id)
            except (ValueError, TypeError):
                return res # Nếu ID là chuỗi dạng virtual new, chưa có trong DB, thì coi như trống lịch sử

            if not numeric_v_id:
                return res
                
            viewing_version = self.env['hr.version'].browse(numeric_v_id)
            employee_versions = all_versions.filtered(
                lambda v: (v.is_approved and (v.date_version < viewing_version.date_version or (v.date_version == viewing_version.date_version and v.id <= viewing_version.id)))
            )
        else:
            employee_versions = all_versions.filtered(lambda v: v.is_approved)

        employee_versions = employee_versions.sorted(key=lambda v: v.date_version)
        if not employee_versions:
            return res

        interval_date_start = False
        for i in range(len(employee_versions) - 1):
            current_version = employee_versions[i]
            next_version = employee_versions[i + 1]
            current_date_start = max(current_version.date_version, current_version.contract_date_start or date.min)
            current_date_end = min(next_version.date_version + relativedelta(days=-1), current_version.contract_date_end or date.max)
            if not current_version.job_title:
                if interval_date_start:
                    previous_version = employee_versions[i - 1]
                    res.append({
                        'id': previous_version.id,
                        'job_title': f"{previous_version.job_title} - {previous_version.department_id.name}" if previous_version.department_id else previous_version.job_title,
                        'date_start': interval_date_start,
                        'date_end': current_date_start + relativedelta(days=-1),
                    })
                    interval_date_start = False
            elif (current_version.job_title, current_version.department_id) != (next_version.job_title, next_version.department_id) or current_date_end + relativedelta(days=1) != next_version.date_version:
                res.append({
                    'id': current_version.id,
                    'job_title': f"{current_version.job_title} - {current_version.department_id.name}" if current_version.department_id else current_version.job_title,
                    'date_start': interval_date_start or current_date_start,
                    'date_end': current_date_end,
                })
                interval_date_start = False
            else:
                interval_date_start = interval_date_start or current_date_start

        last_version = employee_versions[-1]
        if last_version.job_title:
            current_date_start = max(last_version.date_version, last_version.contract_date_start or date.min)
            res.append({
                'id': last_version.id,
                'job_title': f"{last_version.job_title} - {last_version.department_id.name}" if last_version.department_id else last_version.job_title,
                'date_start': interval_date_start or current_date_start,
                'date_end': last_version.contract_date_end or False,
            })
        elif interval_date_start:
            previous_version = employee_versions[-2]
            res.append({
                'id': previous_version.id,
                'job_title': f"{previous_version.job_title} - {previous_version.department_id.name}" if previous_version.department_id else previous_version.job_title,
                'date_start': interval_date_start,
                'date_end': current_date_start + relativedelta(days=-1),
            })
        return res[::-1]

    def write(self, vals):
        # 1. Kiểm tra khóa dữ liệu nếu phiên bản đã duyệt
        allowed_fields = {'version_id', 'current_version_id', 'active', 'message_follower_ids', 'message_ids', 'activity_ids', 'activity_state', 'hr_icon_display', 'show_hr_icon_display', 'last_activity', 'last_activity_time'}
        update_fields = set(vals.keys())
        
        if update_fields - allowed_fields:
            for rec in self:
                if rec.require_version_approval:
                    if 'version_id' in vals:
                        # Nếu có truyền version mới vào đợt lưu này, kiểm tra version mới
                        if vals['version_id']:
                            new_version = self.env['hr.version'].browse(vals['version_id'])
                            if new_version.exists() and new_version.is_approved:
                                raise UserError(_("Phiên bản bạn đang cập nhật đã được duyệt và khóa. Vui lòng tạo phiên bản mới!"))
                    else:
                        if rec.version_is_approved:
                            raise UserError(_("Phiên bản hiện tại đã được duyệt và bị khóa dữ liệu. Để thay đổi thông tin nhân viên, vui lòng tạo phiên bản mới!"))

        # 2. Lưu trạng thái trước khi save
        old_active_states = {rec.id: rec.active for rec in self}

        # Thực hiện write gốc
        res = super().write(vals)
        # Nếu Archive hoặc kích hoạt lại, tính toán lại version hợp lệ
        if 'active' in vals or 'is_approved' in vals:
            for rec in self:
                self._recalc_employee_valid_version(rec)
        # Cập nhật login/email của User nếu work_email thay đổi
        if 'work_email' in vals:
            new_email = vals['work_email']
            for rec in self:
                if rec.user_id:
                    if rec.user_id.login != new_email or rec.user_id.email != new_email:
                        rec.user_id.sudo().with_context(mail_notrack=True).write({
                            'login': new_email,
                            'email': new_email
                        })

        # 1.5 Kích hoạt đồng bộ Quyền nếu thay đổi cấu trúc
        # sync_fields = ['department_id', 'job_id', 'managed_dept_ids', 'concurrent_ids']
        # if any(f in vals for f in sync_fields):
        #     self.env['hr.department'].sudo().add_User2Groups(self)

        # 2. So sánh trạng thái sau khi save
        for rec in self:
            was_active = old_active_states.get(rec.id)
            if was_active != rec.active:
                if not rec.active:
                    old_job = rec.job_id.name if rec.job_id else 'N/A'
                    old_dept = rec.department_id.name if rec.department_id else 'N/A'
                    
                    rec.message_post(
                        body=f"🔴 Nhân viên bị vô hiệu hóa (Archive). <br/>"
                             f"Gỡ khỏi chức vụ: <b>{old_job}</b> <br/>"
                             f"Gỡ khỏi phòng ban: <b>{old_dept}</b>",
                        message_type='notification'
                    )
                    
                    rec.write({
                        'job_id': False,
                        'department_id': False,
                    })

                    if rec.user_id and rec.user_id.active:
                        rec.user_id.sudo().write({'active': False})
                
                elif rec.active:
                    rec.message_post(
                        body="🟢 Nhân viên đã được kích hoạt lại (Unarchive).",
                        message_type='notification'
                    )
                    if rec.user_id and not rec.user_id.active:
                        rec.user_id.sudo().write({'active': True})

        return res
    
    def unlink(self):
        employees_to_sync = self
        res = super().unlink()
        for emp in employees_to_sync:
            if emp.exists():
                self._recalc_employee_valid_version(emp)
        return res
        
    @api.constrains('parent_id')
    def _check_parent_not_loop(self):
        for emp in self:
            if emp.parent_id:
                if emp.parent_id == emp:
                    emp.parent_id = False
                if emp.coach_id == emp:
                    emp.coach_id = False

                if emp.parent_id.parent_id == emp:
                    raise ValidationError(
                        f"Không thể chọn {emp.parent_id.name} làm quản lý vì {emp.name} đã là quản lý của họ."
                    )

                current = emp.parent_id
                while current:
                    if current == emp:
                        raise ValidationError(
                            f"Quan hệ quản lý giữa {emp.name} và {emp.parent_id.name} tạo vòng lặp không hợp lệ."
                        )
                    current = current.parent_id

    @api.constrains('department_id', 'job_id')
    def _check_job_quota(self):
        for rec in self:
            if rec.department_id and rec.job_id:
                dept_job = self.env['hr.department.job'].search([
                    ('department_id', '=', rec.department_id.id),
                    ('job_id', '=', rec.job_id.id)
                ], limit=1)
                
                if dept_job and dept_job.max_employee > 0:
                    domain = [
                        ('department_id', '=', rec.department_id.id),
                        ('job_id', '=', rec.job_id.id),
                        ('id', '!=', rec.id if isinstance(rec.id, int) else 0)
                    ]
                    current_count = self.env['hr.employee'].search_count(domain)
                    
                    if current_count >= dept_job.max_employee:
                        raise ValidationError(
                            _("Chức vụ '%s' tại phòng ban '%s' đã hết biên chế (Tối đa %s nhân viên).") % 
                            (rec.job_id.name, rec.department_id.name, dept_job.max_employee)
                        )

    def action_remove_from_job(self):
        for rec in self:
            rec.write({
                'job_id': False,
                'managed_dept_ids': [fields.Command.clear()]
            })
        return True

    def action_transfer_job(self):
        """Open wizard to transfer this employee's job to another employee."""
        self.ensure_one()
        if not self.job_id:
            raise UserError("Nhân viên này không có chức vụ để chuyển giao.")
        return {
            'name': 'Chuyển giao chức vụ: %s' % self.job_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'hr.job.transfer.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_source_employee_id': self.id,
            }
        }


    @api.model
    def _recalc_employee_valid_version(self, employee):
        if not employee:
            return
        
        # Tìm version hợp lệ gần nhất (đã duyệt, <= hôm nay, đang active)
        # Sử dụng default env (active_test=True) để không bao giờ bốc trúng bản đã bị archive
        latest_valid_version = self.env['hr.version'].search([
            ('employee_id', '=', employee.id),
            ('is_approved', '=', True),
            ('date_version', '<=', fields.Date.today())
        ], order='date_version desc, id desc', limit=1)
        
        new_version_id = latest_valid_version[0].id if latest_valid_version else False
        
        # Nếu current_version_id thay đổi do bị xóa/archive, ta update
        if employee.current_version_id.id != new_version_id:
            employee.current_version_id = new_version_id

class HrResumeLineInherit(models.Model):
    _inherit = 'hr.resume.line'

    version_id = fields.Many2one('hr.version', string="Phiên bản", ondelete="cascade", copy=False)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('version_id') and not vals.get('employee_id'):
                version = self.env['hr.version'].browse(vals['version_id'])
                if version.employee_id:
                    vals['employee_id'] = version.employee_id.id
        return super().create(vals_list)

   