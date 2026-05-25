from odoo import api, models, tools, _, fields
import re
import logging
from odoo.http import request
_logger = logging.getLogger(__name__)
class CulturalLevelCategory(models.Model):
    _name = 'cultural.level.category'
    _description = 'Cultural Level Category'
    
    code = fields.Char(string='Mã Trình Độ Văn Hóa', required=True)
    name = fields.Char(string='Tên Trình Độ Văn Hóa', required=True)
    description = fields.Text(string='Description')