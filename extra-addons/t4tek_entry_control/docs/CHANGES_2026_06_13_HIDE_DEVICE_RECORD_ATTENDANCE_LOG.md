# 2026-06-13 - Hide Device Record from Attendance Logs UI

## Change

Hide the technical `device_id` / **Device Record** field from the `entry.control.attendance.log` form and search views.

## Result

Attendance Logs now show the human-readable device serial/name via `serial_number` only.
The internal `device_id` link is still kept in the database for processing, duplicate checks, and system-generated attendance log handling.

## Scope

- No database column removal
- No API payload change
- No change to attendance processing logic
- UI cleanup only
