# Derived daily checkout without changing Attendance Logs

- API still stores raw Attendance Logs only.
- Attendance Logs keep their server-owned `direction` for traceability.
- `action_sync_hr_attendance()` creates daily `hr.attendance` as a derived summary:
  - first Attendance Log with `direction = in` in the day becomes `check_in`;
  - final raw Attendance Log after that check-in becomes derived `check_out`;
  - the final raw log direction is not rewritten.
- Example: `08:00 Check In`, `08:10 Check Out`, `13:10 Check In` creates `hr.attendance` `08:00 -> 13:10`, while the `13:10` raw log remains `Check In`.
