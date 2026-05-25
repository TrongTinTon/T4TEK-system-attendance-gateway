# Employee Code identifier update

Updated the Odoo module so Attendance Gateway uses the existing SEM field `hr.employee.code` / Mã nhân viên as the Controller and ZKTeco device user identifier.

Important behavior:
- This module no longer creates or redefines `hr.employee.code`.
- The module depends on `SEM`, because SEM already owns the Employee Code field.
- `/api/entry_control/v1/employees` returns:
  - `employee_id`: Employee Code / Mã nhân viên. Controller must use this as the device user ID / ZKTeco EnrollNumber.
  - `employee_code`: same canonical code for clarity.
  - `odoo_employee_id`: numeric Odoo database ID for diagnostics only.
  - `pin`: optional device password/PIN from HR/SEM, not the identifier.
- `/api/entry_control/v1/employees/sync-status` resolves reported `employee_id` by Employee Code.
- Attendance log ingestion resolves incoming `employee_id` by Employee Code first, with numeric Odoo ID fallback only for upgrade compatibility.
- Employee pagination remains unchanged; `page_size` is capped at 100.
