# Next-day real Attendance Logs override generated 00:00 attendance

- `hr.attendance` is always derived from raw Attendance Logs.
- If the previous day generated a carry-over Check In at 00:00 for the next day, and the next day later has real Attendance Logs, the derived attendance is recalculated from those logs.
- The generated 00:00 row is overwritten by the first real Check In from Attendance Logs.
- Reprocessing a previous day will not overwrite an already-derived next-day attendance with 00:00.
- Attendance Logs remain unchanged for audit.
