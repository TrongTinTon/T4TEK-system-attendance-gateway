# Attendance Log Time Display

- Added computed UI field `time_display` with label **Time**.
- `Time` is now calculated as `Attendance Logs.check_time` converted to the module timezone configured by `entry_control.attendance_timezone`.
- Default module timezone remains `Asia/Ho_Chi_Minh`.
- The display rule is the same for real logs and system-generated logs.
- `device_timezone` remains visible only as source/context information: real logs may show `+07:00`, while system-generated logs show `0`.
- `check_time` remains the canonical UTC-naive Odoo Datetime and is not changed by this UI field.
