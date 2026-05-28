# -*- coding: utf-8 -*-
from odoo import fields, models

class ResCompany(models.Model):
    _inherit = 'res.company'

    late_allow_time = fields.Integer(
        string="Cho phép trễ (phút)",
        default=0
    )
    early_allow_time = fields.Integer(
        string="Cho phép về sớm (phút)",
        default=0
    )
