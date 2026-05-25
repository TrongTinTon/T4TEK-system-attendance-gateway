# Latest API logic audit

Current clean API rule:
- Controller authenticates with Controller ID + Secret Key.
- Controller calls Odoo as a client.
- Odoo does not track user-device sync status.
- `/api/entry_control/v1/employees` returns `employee_id = hr.employee.id` and `pin = device password/PIN`.
- Attendance matching uses `employee_id = hr.employee.id`.
