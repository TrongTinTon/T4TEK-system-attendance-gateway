# 19.0.30.48 - Keep Controller Check Time exactly as device local time

- Attendance Logs now store the Controller/device clock time exactly in the single `check_time` field.
- Example: `2026-05-27 08:13:27+07` is stored/displayed as `2026-05-27 08:13:27`, not converted to `01:13` UTC.
- System-generated Attendance Logs `23:59 Check Out` and `00:00 Check In` are also stored as local device clock times.
- Business-day grouping, Create Attendances, and cron now use the stored local Check Time directly.
