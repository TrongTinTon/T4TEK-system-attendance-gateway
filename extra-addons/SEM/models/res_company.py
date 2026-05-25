# -*- coding: utf-8 -*-
from odoo import fields, models

class ResCompany(models.Model):
    _inherit = 'res.company'

    require_version_approval = fields.Boolean(
        string='Bắt buộc duyệt phiên bản',
        default=False
    )
    contract_expiration_notice_period = fields.Integer(
        string='Thông báo hết hạn hợp đồng',
        default=30
    )
    work_permit_expiration_notice_period = fields.Integer(
        string='Thông báo hết hạn GPLĐ',
        default=30
    )
