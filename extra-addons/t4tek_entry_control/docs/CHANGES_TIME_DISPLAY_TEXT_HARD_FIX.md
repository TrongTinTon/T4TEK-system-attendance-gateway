# Time Display Text Hard Fix

- Added a new computed Char field `time_display_text` labeled **Time**.
- Attendance Logs list/form and Controller embedded Attendance Logs now use `time_display_text`, not the older `time_display` field.
- The field formats canonical UTC-naive `check_time` in the module timezone (`entry_control.attendance_timezone`, default `Asia/Ho_Chi_Minh`) as plain text, so Odoo Web cannot apply the current user's timezone a second time or render stale Datetime metadata.
- Example: controller `2026-05-27 13:18:00+07` -> DB `check_time=2026-05-27 06:18:00` -> Time `2026-05-27 13:18:00`.
