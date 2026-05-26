# Daily First Check In / Last Check Out Attendance Creation

Changed `entry.control.attendance.log.action_sync_hr_attendance()` so `hr.attendance` is created/updated per Employee + day instead of per raw log.

Rules:
- First raw log in the day becomes `check_in`.
- Last raw log in the day becomes `check_out`.
- If only one log exists in the day, an open attendance is created with `check_in` only.
- Intermediate logs remain as raw audit records and are linked to the generated attendance.
- API ingestion still stores raw Attendance Logs only; it does not auto-create `hr.attendance`.
