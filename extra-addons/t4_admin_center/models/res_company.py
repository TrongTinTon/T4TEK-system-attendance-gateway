# -*- coding: utf-8 -*-
from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    x_disable_transactional_mail = fields.Boolean(
        related='partner_id.x_disable_transactional_mail',
        string='Tắt thông báo mail giao dịch',
        readonly=False,
        help='Bật tùy chọn này để ngừng gửi các email tự động như đơn hàng, hóa đơn... từ công ty hiện tại.',
    )
