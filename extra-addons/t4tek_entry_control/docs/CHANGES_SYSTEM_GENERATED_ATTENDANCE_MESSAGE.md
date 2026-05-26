# 19.0.30.33 - System generated attendance message

- Added `hr.attendance.message` to mark system-generated attendance times.
- When final checkout is missing, Entry Control creates/checks out at 23:59 for the day.
- When 23:59 checkout is generated, Entry Control also creates a next-day 00:00 check-in.
- Both generated rows are marked in `Message` so users can distinguish them from real device punch data.
- Attendance Logs remain unchanged for audit.
