from odoo import api, models, tools, _, fields
import re
import logging
from odoo.http import request
_logger = logging.getLogger(__name__)

class resCountryStateInherit(models.Model):
    _inherit = 'res.country.state'

    active = fields.Boolean(string='Hoạt động')

    def _compute_display_name(self):
        for record in self:
            record.display_name = record.name
