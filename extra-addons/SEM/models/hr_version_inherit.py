from odoo import api, models, fields, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class HrVersionInherit(models.Model):
    _inherit = 'hr.version'
    _description = 'Employee Version (Extended)'

    is_approved = fields.Boolean(string='Approved', default=False, tracking=True, copy=False)
    approved_by_id = fields.Many2one('res.users', string='Approved by', readonly=True, copy=False)
    approved_date = fields.Datetime(string='Approved on', readonly=True, copy=False)

    resume_line_ids = fields.One2many(
        'hr.resume.line',
        'version_id',
        string='Resume Lines',
        copy=True
    )

    employee_skill_ids = fields.One2many(
        'hr.employee.skill',
        'version_id',
        copy=True
    )

    parent_id = fields.Many2one(
        'hr.employee', 
        string='Quản lý / Cấp trên (Lịch sử)', 
        copy=True,
    )

    @api.constrains('date_version', 'employee_id')
    def _check_date_version_chronology(self):
        for version in self:
            if not version.employee_id or not version.date_version:
                continue
            
            # Lấy các version của nhân viên đó (ngoại trừ version hiện tại)
            other_versions = self.env['hr.version'].search([
                ('employee_id', '=', version.employee_id.id),
                ('id', '!=', version.id)
            ])
            
            # if other_versions:
            #     max_date = max(other_versions.mapped('date_version'))
            #     if version.date_version < max_date:
            #         raise UserError(_("Không được phép đặt mốc thời gian lùi về quá khứ so với thời điểm của phiên bản hiện hữu (%s).") % (max_date.strftime('%d/%m/%Y')))

    def action_approve(self):
        for version in self:
            if version.is_approved:
                continue
            version.write({
                'is_approved': True,
                'approved_by_id': self.env.user.id,
                'approved_date': fields.Datetime.now()
            })
        return True

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.company.require_version_approval:
            records.action_approve()
        return records

    @api.depends('version_ids.date_version', 'version_ids.active', 'active')
    def _compute_current_version_id(self):
        for employee in self:
            version = self.env['hr.version'].search(
                [('employee_id', 'in', employee.ids), ('date_version', '<=', fields.Date.today())],
                order='date_version desc',
                limit=1,
            )
            # if employee.current_date_version > version.date_version:
            #     return
            new_current_version = False
            if version:
                new_current_version = version
            elif employee.version_ids:
                new_current_version = employee.version_ids[0]
            # To not trigger computed properties if still the same version
            if employee.current_version_id != new_current_version:
                employee.current_version_id = new_current_version

    def write(self, vals):
        # Always allow write, saving data correctly
        return super().write(vals)