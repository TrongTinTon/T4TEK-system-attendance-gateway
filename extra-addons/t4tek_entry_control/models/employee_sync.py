from odoo import fields, models


class EntryControlEmployeeSync(models.Model):
    _name = "entry.control.employee.sync"
    _description = "Entry Control Employee Sync Status"
    _order = "last_synced_at desc, id desc"

    controller_id = fields.Many2one("entry.control.controller", required=True, ondelete="cascade", index=True)
    employee_id = fields.Many2one("hr.employee", required=True, ondelete="cascade", index=True)
    pin = fields.Char(string="Device Password/PIN", index=True)
    employee_name = fields.Char()
    last_synced_at = fields.Datetime()
    sync_status = fields.Selection([
        ("pending", "Pending"),
        ("success", "Success"),
        ("failed", "Failed"),
        ("skipped", "Skipped"),
    ], default="pending", index=True)
    error_message = fields.Text()

    _sql_constraints = [
        ("controller_employee_unique", "unique(controller_id, employee_id)", "Employee Sync Status must be unique per Controller."),
    ]
