from odoo import fields, models


class HrAttendance(models.Model):
    _inherit = "hr.attendance"

    message = fields.Text(string="Message", readonly=True)
