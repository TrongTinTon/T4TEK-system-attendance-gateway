# Remove redundant odoo_employee_id

- Removed `odoo_employee_id` from `/api/entry_control/v1/employees` response.
- `employee_id` is now the only canonical identifier and equals `hr.employee.id`.
- `pin` remains the device password/PIN.
