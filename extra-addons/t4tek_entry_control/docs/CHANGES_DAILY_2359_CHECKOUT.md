# Daily Attendance: Generated 23:59 Check Out

## Changed

`entry.control.attendance.log.action_sync_hr_attendance()` now creates the derived `hr.attendance` record as:

- `check_in` = first Attendance Log of the day with `direction = in`.
- `check_out` = generated server-side value `23:59:00` of that same day.

## Preserved

- Attendance Logs remain the raw audit trail.
- Attendance Logs `direction`, `check_time`, `check_type`, and other raw fields are not changed.
- API log ingestion still only creates Attendance Logs and does not auto-create `hr.attendance`.
- Manual list-view `Create Attendances` and daily cron use the same derived logic.
