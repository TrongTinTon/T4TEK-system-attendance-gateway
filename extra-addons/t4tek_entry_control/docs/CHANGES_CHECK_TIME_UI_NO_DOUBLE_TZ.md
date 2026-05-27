# 19.0.30.52 - Check Time UI without double timezone

- Keep a single stored Attendance Log Check Time column (`check_time`) as exact device-local wall time.
- Keep `device_timezone` as timezone context, for example `+07:00`.
- Add non-stored UI display field `check_time_display` labeled `Check Time` so Odoo web UI does not add user timezone again.
- System-generated `23:59 Check Out` and `00:00 Check In` now display exactly as 23:59 and 00:00 in Attendance Logs.
- No new database column is added for the display field.
