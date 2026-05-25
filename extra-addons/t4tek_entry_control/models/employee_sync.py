from odoo import fields, models


class EntryControlEmployeeSync(models.Model):
    _name = "entry.control.employee.sync"
    _description = "Entry Control Employee Sync Status"
    _order = "last_synced_at desc, id desc"

    controller_id = fields.Many2one("entry.control.controller", required=True, ondelete="cascade", index=True)
    employee_id = fields.Many2one("hr.employee", required=True, ondelete="cascade", index=True)
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

    def init(self):
        # The latest clean design does not need to store/display the device
        # password/PIN in Employee Sync Status. Keep upgrades safe by removing
        # the old column when it exists.
        self.env.cr.execute("ALTER TABLE IF EXISTS entry_control_employee_sync DROP COLUMN IF EXISTS pin")
