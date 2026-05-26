from odoo import fields, models


class HrAttendance(models.Model):
    _inherit = "hr.attendance"

    message = fields.Text(
        string="Message",
        readonly=True,
        help="Entry Control note for attendance rows generated or adjusted by the system.",
    )
