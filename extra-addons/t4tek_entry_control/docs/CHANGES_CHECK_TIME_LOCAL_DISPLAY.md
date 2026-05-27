# Check Time local display fix

- Keep `check_time` stored internally as Odoo-standard naive UTC for domains, cron, and hr.attendance creation.
- Add computed `check_time_local` for Attendance Logs UI display in `entry_control.attendance_timezone` (default `Asia/Ho_Chi_Minh`).
- Attendance Logs list/form now shows local Check Time first and keeps UTC Check Time as technical/hidden field.
