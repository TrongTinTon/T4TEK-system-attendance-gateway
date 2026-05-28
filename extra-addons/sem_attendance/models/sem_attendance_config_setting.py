from odoo import fields, models

class SemAttendanceConfigSettings(models.TransientModel):
    _name = 'sem.attendance.config.settings'
    _description = 'Cấu hình Chấm công SEM'

    company_id = fields.Many2one(
        'res.company', 
        string='Công ty', 
        required=True, 
        default=lambda self: self.env.company
    )

    late_allow_time = fields.Integer(
        string="Cho phép trễ (phút)",
        related='company_id.late_allow_time',
        readonly=False
    )
    early_allow_time = fields.Integer(
        string="Cho phép về sớm (phút)",
        related='company_id.early_allow_time',
        readonly=False
    )

    def execute(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Thành công',
                'message': 'Đã tải & lưu cấu hình áp dụng cho ' + self.company_id.name,
                'type': 'success',
                'sticky': False,
            }
        }
