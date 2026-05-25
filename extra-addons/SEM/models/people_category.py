from odoo import api, models, tools, _, fields
import re
import logging
from odoo.http import request
_logger = logging.getLogger(__name__)

class PeopleCategory(models.Model):
    _name = 'people.category'
    _description = 'People Category'

    code = fields.Char(string='Mã Dân Tộc', required=True)
    name = fields.Char(string='Tên Dân Tộc', required=True)
    description = fields.Text(string='Description')



