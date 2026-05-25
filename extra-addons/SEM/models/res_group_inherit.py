from odoo import api, models, tools, _, fields
import re
import logging
from odoo.http import request
_logger = logging.getLogger(__name__)

class resGroupInherit(models.Model):
    _inherit = 'res.groups'

    #department_ids = fields.Many2many('hr.department', string='Departments', help='Departments associated with this group.')