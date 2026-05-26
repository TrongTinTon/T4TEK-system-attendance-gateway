# Daily attendance derived checkout rule update

This build keeps Attendance Logs as the audit trail and does not rewrite their `direction` values.

When creating `hr.attendance` from Attendance Logs, the system now derives one daily attendance per employee/day:

- `check_in` = first Attendance Log of the day with `direction = in`.
- `check_out` = if the final log after that `check_in` is `direction = out`, use that final Check Out time.
- Otherwise, generate `check_out = 23:59:00` on the same day.

Examples:

- `08:00 Check In` -> `08:00 / 23:59`.
- `08:00 Check In`, `08:10 Check Out`, `13:10 Check In` -> `08:00 / 23:59`.
- `08:00 Check In`, `17:10 Check Out` -> `08:00 / 17:10`.

Both the manual `Create Attendances` wizard and the daily cron use the same `action_sync_hr_attendance()` method.
