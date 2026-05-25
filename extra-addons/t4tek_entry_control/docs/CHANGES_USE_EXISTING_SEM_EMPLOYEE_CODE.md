# Use existing SEM Employee Code

Reason:
The customer already installed the SEM module, which defines `hr.employee.code` as `Mã nhân viên`. Attendance Gateway should not define the same field again.

Changes:
- Removed the `hr.employee.code` field definition from Attendance Gateway.
- Removed the Attendance Gateway employee form extension that displayed duplicate Code/PIN fields, because SEM already displays them.
- Added `SEM` as a module dependency so `hr.employee.code` is available before Attendance Gateway uses it.
- Kept API contract: `employee_id` in API payloads means Employee Code, not numeric Odoo employee ID.
- Kept `odoo_employee_id` only as diagnostic metadata.
