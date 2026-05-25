from odoo import api, models, tools, _, fields
import re
import logging
from odoo.http import request
from odoo.exceptions import ValidationError, UserError
_logger = logging.getLogger(__name__)

class SEMWorkLocationInherit(models.Model):
    _inherit = 'hr.work.location'

    allowed_address_ids = fields.Many2many(
        'res.partner',
        compute='_compute_allowed_address_ids',
        string='Allowed Addresses',
    )

    @api.depends('company_id')
    def _compute_allowed_address_ids(self):
        for rec in self:
            company = rec.company_id or self.env.company
            company_partner = company.partner_id
            # Only get child contacts that are NOT linked to a res.company
            # (child companies' partners are also child_ids but should be excluded)
            child_partners = company_partner.child_ids.filtered(
                lambda p: not p.ref_company_ids
            )
            rec.allowed_address_ids = company_partner | child_partners

    @api.onchange('company_id')
    def _onchange_company_id_clear_address(self):
        self.address_id = False

    @api.constrains('address_id', 'company_id')
    def _check_address_in_company(self):
        for rec in self:
            if rec.address_id and rec.allowed_address_ids and rec.address_id not in rec.allowed_address_ids:
                raise ValidationError(
                    _("Khu vực '%s' không thuộc danh sách khu vực của công ty '%s'. "
                      "Vui lòng chọn khu vực đã được khai báo trong Danh sách khu vực của công ty.")
                    % (rec.address_id.display_name, (rec.company_id or self.env.company).name)
                )
