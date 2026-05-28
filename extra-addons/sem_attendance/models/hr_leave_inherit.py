from odoo import api, models, fields, _
from datetime import time
import logging

class HrLeave(models.Model):
    _inherit = 'hr.leave'
    
    