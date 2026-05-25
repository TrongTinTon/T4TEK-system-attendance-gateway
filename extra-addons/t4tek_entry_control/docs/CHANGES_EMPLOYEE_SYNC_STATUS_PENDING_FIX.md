# Employee Sync Status pending overwrite fix

- `/api/entry_control/v1/employees` no longer overwrites an already successful Employee Sync Status row on every pull.
- Existing `success/skipped` rows are preserved unless the related `hr.employee.write_date` is newer than `last_synced_at`.
- `/employees/sync-status` now accepts ISO datetime values from the Controller and normalizes them for Odoo Datetime fields.
- Added response counters `employee_sync_status_pending` and `employee_sync_status_preserved`.
