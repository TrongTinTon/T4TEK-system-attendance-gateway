# -*- coding: utf-8 -*-
from odoo import fields, models, api
import logging

_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _inherit = 'res.partner'

    x_disable_transactional_mail = fields.Boolean(
        string='Tắt thông báo mail giao dịch',
        default=False,
        help=(
            'Nếu được bật, đối tác này sẽ KHÔNG nhận email từ các giao dịch '
            'như đơn bán hàng, đơn mua hàng, hóa đơn, v.v.\n'
            'Các email liên quan đến tài khoản (đăng ký, quên mật khẩu) '
            'vẫn được gửi bình thường.'
        ),
    )

    ref_company_ids = fields.One2many(
        'res.company', 'partner_id',
        string='Công ty liên kết',
    )
