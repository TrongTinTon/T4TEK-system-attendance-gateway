# HR Employee ID canonical API fix

- `/api/entry_control/v1/employees` now returns `employee_id` as the canonical `hr.employee.id`.
- `pin` is treated as the device password/PIN, not as the ZKTeco user identifier.
- Controller should use `employee_id` as the ZKTeco EnrollNumber/User ID when writing users to devices.
- `/employees/sync-status` and `/attendance/logs/push` match employees by `hr.employee.id`.
- Legacy fallback by PIN remains only to avoid breaking older payloads.
