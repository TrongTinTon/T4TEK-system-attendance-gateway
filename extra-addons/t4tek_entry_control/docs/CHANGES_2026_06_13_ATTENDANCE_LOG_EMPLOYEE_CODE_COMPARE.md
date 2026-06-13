# 2026-06-13 - Attendance Logs: Employee Code Compare Columns

## What changed

Attendance Logs now include optional display columns for audit/reconciliation:

- Controller: stored related Controller name from `controller_id`.
- Employee Code (Server): code currently stored on the matched `hr.employee` record.
- Employee Code (Controller): raw employee code/ID value received from the Controller payload.

## Why

This lets operators compare whether the Controller sent the same employee code as the server master data directly in the Attendance Logs list/form view.

## Ingestion behavior

The attendance push API now accepts and preserves these Controller-side keys as `employee_code_controller`:

- `employee_id`
- `employeeId`
- `employee_code`
- `employeeCode`
- `enroll_number`
- `enrollNumber`
- `user_id`
- `userId`

The same value is still used to map to the server-side Employee record. Existing duplicate logs are updated with the Controller employee code if the field was previously blank.

## UI

The new fields are available in Attendance Logs list, form, and search views. In the list view they are marked as optional columns so each user can show/hide them from the column chooser.
