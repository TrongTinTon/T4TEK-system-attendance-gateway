# Time display list cleanup

- Attendance Logs list now shows `Time` only for the visible attendance timestamp.
- Raw `check_time` remains stored as canonical UTC-naive and is kept on the form as `Check Time (UTC Storage)` for technical verification.
- Controller embedded Attendance Logs list also hides raw `check_time` to avoid confusion with Odoo user-timezone rendering.
- `time_display` continues to convert UTC-naive `check_time` to the configured module timezone (`entry_control.attendance_timezone`, default `Asia/Ho_Chi_Minh`).
