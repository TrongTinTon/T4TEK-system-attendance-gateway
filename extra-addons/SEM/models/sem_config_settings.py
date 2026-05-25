# -*- coding: utf-8 -*-
from odoo import fields, models

class SemConfigSettings(models.TransientModel):
    _name = 'sem.config.settings'
    _description = 'Cấu hình SEM'

    company_id = fields.Many2one(
        'res.company', 
        string='Công ty', 
        required=True, 
        default=lambda self: self.env.company
    )

    require_version_approval = fields.Boolean(
        string='Bắt buộc duyệt phiên bản',
        related='company_id.require_version_approval',
        readonly=False
    )
    contract_expiration_notice_period = fields.Integer(
        string='Thông báo hết hạn hợp đồng (Ngày)',
        related='company_id.contract_expiration_notice_period',
        readonly=False
    )
    work_permit_expiration_notice_period = fields.Integer(
        string='Thông báo hết hạn GPLĐ (Ngày)',
        related='company_id.work_permit_expiration_notice_period',
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
