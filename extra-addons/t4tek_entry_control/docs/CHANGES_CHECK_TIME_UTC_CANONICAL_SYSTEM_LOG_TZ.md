# Check Time timezone canonical fix

- Attendance Logs keep a single field: `check_time` / Check Time.
- Controller values with timezone, e.g. `2026-05-27 07:47:06+07`, are stored as Odoo UTC-naive datetime and display back as local time for Vietnam users.
- Naive controller/device times are treated as `entry_control.attendance_timezone` local time.
- System-generated 23:59 Check Out and 00:00 next-day Check In are now converted from business local time to UTC before writing. This prevents UI display such as 06:59 / 07:00.
- No extra Check Time UTC / Device Check Time columns are reintroduced.
