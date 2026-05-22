# 19.0.20 Attendance Direction Inference

## Goal

Keep the exact direction data sent by the ZKTeco device while allowing Odoo HR Attendances to create more useful Check In / Check Out pairs when the device always sends AttState/InOutMode = 0.

## Added fields on Attendance Logs

- `device_check_type`: raw value sent by the Controller/device.
- `device_direction`: direction mapped directly from the device value.
- `resolved_direction`: final direction used to create/update `hr.attendance`.
- `direction_source`: `device`, `software_inferred`, or `hybrid`.

The legacy `check_type` and `attendance_direction` fields are kept for compatibility. `attendance_direction` now mirrors `resolved_direction`.

## Controller setting

Added `attendance_direction_mode` on Controllers:

- `device`: trust ZKTeco AttState/InOutMode.
- `software_inferred`: ignore device direction and infer from open HR Attendance.
- `hybrid`: trust explicit device Check-Out values; infer direction when the device sends Check-In Default/0. This is the default.

## HR Attendance behavior

When `resolved_direction` is `in`, a new `hr.attendance` check-in is created if no open attendance exists.

When `resolved_direction` is `out`, the latest open attendance for the employee is closed with the log time.

## API response

`/api/entry_control/v1/attendance/logs/push` now returns direction details per log:

- `device_check_type`
- `device_direction`
- `resolved_direction`
- `direction_source`
