# Attendance Log - Archived Employee Check

## Change

Attendance Log ingestion now searches `hr.employee` with `active_test=False` when resolving the Employee Code sent by the Controller.

## Behavior

- If the Employee Code matches an active employee, the log is linked to `hr.employee` as before.
- If the Employee Code matches an archived/inactive employee, the raw `Employee Code (Controller)` is still stored, but `employee_id` is left empty.
- Archived employee logs are marked `sync_status = skipped` with an explanatory message, so daily attendance generation will not create/update attendance records for archived employees.
- If the Employee Code is not found at all, behavior remains unchanged: the raw Controller code is stored and the log is not linked to `hr.employee`.

## Reason

Odoo's default search context hides archived employees. Without `active_test=False`, the system could not distinguish between an unknown employee code and a code belonging to an archived employee.
