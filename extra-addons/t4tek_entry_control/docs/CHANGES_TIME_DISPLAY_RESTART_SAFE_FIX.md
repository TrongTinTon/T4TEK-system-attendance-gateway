# Time Display restart-safe fix

- Reverted XML views to use existing field `time_display` instead of newly introduced `time_display_text`.
- This avoids Odoo view validation error when the server process has not restarted and the Python registry has not loaded new fields yet.
- `time_display` remains a Char computed field: UTC-naive `check_time` is formatted in module timezone `entry_control.attendance_timezone` / default `Asia/Ho_Chi_Minh`.
- After replacing Python code, restart Odoo and then upgrade the module.
