# Superseded employee identifier note

This note is superseded by `CHANGES_HR_EMPLOYEE_ID_CANONICAL.md`.

Current rule:
- `employee_id` in API payloads is the canonical `hr.employee.id`.
- `pin` is the device password/PIN, not the ZKTeco user identifier.
- Controller should use `employee_id` as the ZKTeco EnrollNumber/User ID when creating users on devices.
