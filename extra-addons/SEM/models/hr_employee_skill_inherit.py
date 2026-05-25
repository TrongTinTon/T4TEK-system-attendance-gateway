from odoo import models, fields, api

class HrEmployeeSkillInherit(models.Model):
    _inherit = 'hr.employee.skill'

    version_id = fields.Many2one('hr.version', string="Phiên bản", ondelete="cascade", copy=False)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('version_id') and not vals.get('employee_id'):
                version = self.env['hr.version'].browse(vals['version_id'])
                if version.employee_id:
                    vals['employee_id'] = version.employee_id.id
        return super().create(vals_list)

    @api.constrains('skill_id', 'skill_type_id', 'skill_level_id', 'valid_from', 'valid_to', 'employee_id')
    def _check_not_overlapping_regular_skill(self):
        # Tắt bỏ hoàn toàn ràng buộc trùng lặp Kỹ năng của Odoo nguyên bản
        # Bởi vì hệ thống Versioning cho phép nhân viên có vô số kỹ năng giống nhau nằm rải rác ở các phiên bản (version_id) khác nhau
        pass
