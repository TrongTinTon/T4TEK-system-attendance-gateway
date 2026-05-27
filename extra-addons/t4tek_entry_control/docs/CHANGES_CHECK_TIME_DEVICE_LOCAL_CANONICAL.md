# 19.0.30.51 - Check Time stores exact Controller/device local time

- Attendance Logs `check_time` now stores the exact wall-clock time sent by the Controller.
  Example: `2026-05-27 08:41:26+07` is stored/displayed as `2026-05-27 08:41:26`.
- `device_timezone` stores the timezone context, for example `+07:00`.
- System-generated `23:59 Check Out` and `00:00 Check In` logs are stored as exact local wall-clock times too.
- Business-day grouping, Create Attendances, and cron calculations now use stored device-local Check Time from Attendance Logs as the source of truth.
