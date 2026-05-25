from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError, AccessError

class HRDepartmentJob(models.Model):
    _name = 'hr.department.job'
    _description = 'Cấu hình Chức vụ theo Phòng ban'
    _order = 'department_id, level, job_id'

    department_id = fields.Many2one('hr.department', string='Phòng ban', required=True, ondelete='cascade')
    job_id = fields.Many2one('hr.job', string='Chức vụ', required=True, ondelete='cascade')

    managed_dept_ids = fields.Many2many('hr.department', string='Phòng ban trực thuộc', domain="[('parent_id', '=', department_id)]")
    is_manager = fields.Boolean(string='Là Trưởng phòng', help="Nếu được chọn, nhân viên giữ chức vụ này sẽ là Manager của phòng ban.")
    is_restricted = fields.Boolean(string='Giới hạn quyền', help="Nếu được chọn, chức vụ này sẽ không được nhận thêm Role từ các phòng ban trực thuộc.")
    

    company_id = fields.Many2one('res.company', string='Công ty', related='department_id.company_id', store=True)

    max_employee = fields.Integer(string='Định biên tối đa', default=0, help="Số lượng nhân viên tối đa cho vị trí này tại phòng ban này. 0 = Không giới hạn.")
    
    level = fields.Integer(string='Cấp bậc', default=10, help="Cấp bậc phân cấp chức vụ. Số càng nhỏ = cấp càng cao.")
    
    @api.constrains('max_employee')
    def _check_max_employee(self):
        for rec in self:
            if rec.max_employee < 0:
                raise ValidationError("Định biên tối đa không thể là số âm.")
            if rec.max_employee != 0 and rec.max_employee < rec.no_of_employee:
                raise ValidationError("Định biên tối đa (%s) không thể thấp hơn số lượng nhân viên thực tế (%s) đang giữ chức vụ này." % (rec.max_employee, rec.no_of_employee))    
    no_of_employee = fields.Integer(
        string='Số lượng nhân viên',
        compute='_compute_employee_stats',
        help='Số lượng nhân viên đang giữ chức vụ này trong phòng ban này.'
    )
    can_add_employee = fields.Boolean(compute='_compute_employee_stats')

    member_ids = fields.Many2many(
        'hr.employee', 
        compute='_compute_member_ids', 
        inverse='_inverse_member_ids',
        string='Nhân viên'
    )

    @api.onchange('is_manager')
    def _onchange_is_manager(self):
        if self.is_manager:
            self.max_employee = 1

    def _compute_member_ids(self):
        """Compute the list of employees holding this job in this department."""
        for rec in self:
            rec.member_ids = self.env['hr.employee'].search([
                ('job_id', '=', rec.job_id.id),
                ('department_id', '=', rec.department_id.id)
            ])

    def _inverse_member_ids(self):
        """Sync inline additions/removals and handle manager assignment."""
        for rec in self:
            current_emps = self.env['hr.employee'].search([
                ('job_id', '=', rec.job_id.id),
                ('department_id', '=', rec.department_id.id)
            ])
            new_emps = rec.member_ids
            
            added = new_emps - current_emps
            removed = current_emps - new_emps
            
            # Quota validation
            max_value = 1 if rec.is_manager else rec.max_employee
            if added and max_value > 0:
                projected_count = len(current_emps) + len(added)
                if projected_count > max_value:
                    raise ValidationError(
                        "Hành động bị chặn: Bạn chỉ có thể thêm tối đa %s nhân viên nữa vào chức vụ này (Định biên %s)." % 
                        (max_value - len(current_emps), max_value)
                    )

            if added:
                added.write({
                    'department_id': rec.department_id.id,
                    'job_id': rec.job_id.id
                })
                for emp in added:
                    emp.message_post(
                        body=f"Đã được bổ nhiệm chức vụ: <b>{rec.job_id.name}</b> tại phòng ban {rec.department_id.name}.",
                        message_type='notification'
                    )
                
                # Sync Manager ID if this is a manager position
                if rec.is_manager:
                    rec.department_id.manager_id = added[0].id

            if removed:
                removed.write({
                    'job_id': False,
                    'managed_dept_ids': [fields.Command.clear()]
                })
                for emp in removed:
                    emp.message_post(
                        body=f"Đã được gỡ khỏi chức vụ: <b>{rec.job_id.name}</b>.",
                        message_type='notification'
                    )
                
                # Clear Manager ID if it was this employee
                if rec.is_manager:
                    if rec.department_id.manager_id in removed:
                        rec.department_id.manager_id = False

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        return records

    def write(self, vals):
        # Authority check: Only Dept Manager or Admin
        if not self.env.su:
            for rec in self:
                restricted_fields = ['managed_dept_ids', 'is_manager', 'is_restricted']
                if any(f in vals for f in restricted_fields):
                    is_dept_manager = rec.department_id.manager_id.user_id == self.env.user
                    is_system_admin = self.env.user.has_group('base.group_system')
                    is_erp_manager = self.env.user.has_group('base.group_erp_manager')
                    
                    if not (is_dept_manager or is_system_admin or is_erp_manager):
                        raise AccessError("Chỉ Trưởng phòng ban hoặc Quản trị viên hệ thống mới có quyền thay đổi cấu hình quản lý của vị trí này.")
        
        # Enforce quota 1 for manager
        if vals.get('is_manager'):
            vals['max_employee'] = 1
            
        res = super().write(vals)

        return res

    @api.depends('member_ids', 'max_employee', 'is_manager')
    def _compute_employee_stats(self):
        """Compute headcount and quota status."""
        for rec in self:
            count = len(rec.member_ids)
            rec.no_of_employee = count
            rec.can_add_employee = rec.max_employee == 0 or count < rec.max_employee

    @api.constrains('is_manager', 'department_id')
    def _check_unique_manager(self):
        for rec in self:
            if rec.is_manager:
                domain = [
                    ('department_id', '=', rec.department_id.id),
                    ('is_manager', '=', True),
                    ('id', '!=', rec.id)
                ]
                if self.search_count(domain):
                    raise ValidationError("Phòng ban '%s' đã có một chức vụ được thiết lập là Trưởng phòng. Mỗi phòng ban chỉ được phép có duy nhất một chức vụ Trưởng phòng." % rec.department_id.name)

    _sql_constraints = [
        ('dept_job_unique', 'unique(department_id, job_id)', 'Chức vụ này đã được khai báo cho phòng ban này!')
    ]

    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, rec.job_id.name))
        return result

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.job_id.name

    def unlink(self):
        # Protection: Trưởng phòng không được xóa chức vụ mình đang nắm giữ
        if not self.env.su:
            current_emp = self.env['hr.employee'].sudo().search([
                ('user_id', '=', self.env.user.id)
            ], limit=1)
            if current_emp:
                is_system_admin = self.env.user.has_group('base.group_system')
                if not is_system_admin:
                    for rec in self:
                        if current_emp.department_id.id == rec.department_id.id and current_emp.job_id.id == rec.job_id.id:
                            raise UserError("Bạn không thể xóa chức vụ mà mình đang nắm giữ. Vui lòng sử dụng chức năng 'Chuyển giao chức vụ' trước.")

        # Collect data for post-deletion sync
        affected_emps = self.mapped('member_ids')

        # 1. Clear fields from employees
        for rec in self:
            employees = self.env['hr.employee'].sudo().search([
                ('department_id', '=', rec.department_id.id),
                ('job_id', '=', rec.job_id.id)
            ])
            if employees:
                employees.write({
                    'job_id': False,
                    'managed_dept_ids': [fields.Command.clear()]
                })
        
        # 2. Delete the actual records
        res = super().unlink()

        return res

    def action_show_employees(self):
        """Open the members list form view."""
        self.ensure_one()
        return {
            'name': ('Nhân viên nắm giữ: %s') % self.job_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'hr.department.job',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref('SEM.view_hr_department_job_members_form').id, 'form')],
            'target': 'new',
            'context': {
                'active_test': False,
            }
        }


