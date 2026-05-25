from odoo import api, models, _, fields
from odoo.exceptions import ValidationError, AccessError
import logging
_logger = logging.getLogger(__name__)


class SEMDepartmentInherit(models.Model):
    _inherit = 'hr.department'

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        if not self.env.is_superuser() and not self.env.user.has_group('SEM.sem_department'):
            if view_type in ['form', 'list', 'kanban', 'hierarchy', 'tree']:
                raise AccessError(_('Bạn không có quyền truy cập giao diện Phòng Ban.'))
        return super().get_view(view_id=view_id, view_type=view_type, **options)


    dept_job_ids = fields.One2many('hr.department.job', 'department_id', string='Cấu hình Chức vụ')

    # valid_manager_ids = fields.Many2many('hr.employee', compute='_compute_valid_manager_ids')

    # @api.depends('dept_job_ids', 'dept_job_ids.member_ids', 'dept_job_ids.is_manager')
    # def _compute_valid_manager_ids(self):
    #     for rec in self:
    #         manager_jobs = rec.dept_job_ids.filtered(lambda j: j.is_manager)
    #         rec.valid_manager_ids = [fields.Command.set(manager_jobs.member_ids.ids)]

    # Fields for "Add Employee" feature
    add_employee_ids = fields.Many2many('hr.employee', 'hr_department_add_emp_rel', 'dept_id', 'emp_id', string='Nhân viên để thêm')
    add_emp_has_conflict = fields.Boolean(string='Xung đột phòng ban')
    add_emp_conflict_msg = fields.Text(string='Thông báo xung đột')
    add_emp_confirmed = fields.Boolean(string='Xác nhận chuyển')

    def action_add_employee_wizard(self):
        self.ensure_one()
        self.write({
            'add_employee_ids': [(6, 0, [])],
            'add_emp_has_conflict': False,
            'add_emp_conflict_msg': False,
            'add_emp_confirmed': False,
        })
        return {
            'name': _('Thêm nhân viên vào phòng ban'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.department',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('SEM.view_department_add_employee_popup_form').id,
            'target': 'new',
            'context': self.env.context,
        }

    def action_add_employee_apply(self):
        self.ensure_one()

        if not self.add_employee_ids:
            return {'type': 'ir.actions.act_window_close'}

        conflicting = self.add_employee_ids.filtered(
            lambda e: e.department_id and e.department_id != self
        )

        if conflicting and not self.add_emp_confirmed:
            names = ", ".join(conflicting.mapped('name'))
            self.write({
                'add_emp_has_conflict': True,
                'add_emp_conflict_msg': _("Các nhân viên sau đã thuộc phòng ban khác: %s. Bạn có muốn chuyển họ sang phòng ban %s không?") % (names, self.name),
                'add_emp_confirmed': True,
            })
            return {
                'name': _('Xác nhận chuyển phòng ban'),
                'type': 'ir.actions.act_window',
                'res_model': 'hr.department',
                'res_id': self.id,
                'view_mode': 'form',
                'view_id': self.env.ref('SEM.view_department_add_employee_popup_form').id,
                'target': 'new',
                'context': self.env.context,
            }

        for emp in self.add_employee_ids:
            old_dept = emp.department_id
            if old_dept and old_dept != self:
                emp.message_post(
                    body=_("Đã chuyển từ phòng ban %s sang %s.") % (old_dept.name, self.name),
                    message_type='notification'
                )
            emp.write({
                'department_id': self.id,
                'job_id': False if old_dept and old_dept != self else emp.job_id.id
            })

        self.write({
            'add_employee_ids': [(6, 0, [])],
            'add_emp_has_conflict': False,
            'add_emp_conflict_msg': False,
            'add_emp_confirmed': False,
        })

        return {'type': 'ir.actions.act_window_close'}
