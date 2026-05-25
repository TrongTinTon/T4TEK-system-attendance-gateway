from odoo import api, models, tools, _, fields
import re
import logging
from odoo.http import request
_logger = logging.getLogger(__name__)

class religionCategory(models.Model):
    _name = 'religion.category'
    _description = 'Religion Category'

    code = fields.Char(string='Mã Tôn Giáo', required=True)
    name = fields.Char(string='Tên Tôn Giáo', required=True)
    description = fields.Text(string='Description')