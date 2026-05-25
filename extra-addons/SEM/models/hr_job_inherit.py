from odoo import api, models, fields, _
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

class HRJobInherit(models.Model):
    _inherit = 'hr.job'
    _description = 'Vị trí phòng ban (Chức vụ)'

    # Hierarchy
    parent_id = fields.Many2one('hr.job', string='Chức vụ cấp trên', index=True, ondelete='restrict')
    child_ids = fields.One2many('hr.job', 'parent_id', string='Chức vụ cấp dưới')

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for job in self:
            if job.parent_id:
                job.complete_name = '%s / %s' % (job.parent_id.complete_name, job.name)
            else:
                job.complete_name = job.name

    complete_name = fields.Char('Complete Name', compute='_compute_complete_name', store=True)

    def name_get(self):
        result = []
        for job in self:
            name = job.complete_name or job.name
            result.append((job.id, name))
        return result