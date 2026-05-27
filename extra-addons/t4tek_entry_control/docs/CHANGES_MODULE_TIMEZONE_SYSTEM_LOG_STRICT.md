# Module timezone strict system log fix

- Added default `ir.config_parameter` data for `entry_control.attendance_timezone = Asia/Ho_Chi_Minh`.
- System-generated Attendance Logs now calculate 23:59 / 00:00 strictly from the module timezone, not from the source device log timezone.
- System-generated Attendance Logs still save `device_timezone = 0` as a marker.
- Marker `0` continues to fall back to module timezone for local-day calculations.

Expected result with `Asia/Ho_Chi_Minh`:

- `2026-05-27 23:59` local -> `check_time = 2026-05-27 16:59:00` UTC-naive, `device_timezone = 0`.
- `2026-05-28 00:00` local -> `check_time = 2026-05-27 17:00:00` UTC-naive, `device_timezone = 0`.
