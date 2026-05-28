from odoo import api, models, tools, _, fields
import re
import logging
from odoo.http import request
_logger = logging.getLogger(__name__)

class AttendanceType(models.Model):
    _name = 'hr.atttendance.type'
    _description = 'Loại Công'

    code = fields.Char(string='Mã Công', required=True)
    name = fields.Char(string='Tên Loại Công', required=True)
    coefficient = fields.Float(string='Hệ số')
    company_id = fields.Many2one('res.company', string='Công ty', default=lambda self: self.env.company, required=True)
    description = fields.Text(string='Description')