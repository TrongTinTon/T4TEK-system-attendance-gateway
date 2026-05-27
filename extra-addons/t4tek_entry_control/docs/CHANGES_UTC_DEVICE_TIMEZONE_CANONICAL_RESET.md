# UTC + Device Timezone Canonical Reset

Baseline reset for Attendance Logs timezone handling.

- Controller value `2026-05-27 10:02:38+07` is stored as `check_time = 2026-05-27 03:02:38` and `device_timezone = +07:00`.
- System-generated local boundary `23:59 Check Out` with `+07:00` is stored as UTC `16:59` and displays as local `23:59`.
- System-generated local boundary `00:00 Check In` with `+07:00` is stored as UTC `17:00` on the previous UTC date and displays as local `00:00`.
- Attendance day grouping uses each log's `device_timezone`, not raw UTC calendar date.
- Old controller comments that treated timezone as note-only were removed/updated.
