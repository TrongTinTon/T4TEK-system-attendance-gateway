# Create Attendances from Attendance Logs

- API `/api/entry_control/v1/attendance/logs/push` now only stores raw Attendance Logs.
- It no longer calls `action_sync_hr_attendance()` automatically when receiving logs.
- Direction logic remains unchanged from the existing source.
- Added the **Create Attendances** button to the Attendance Logs list view.
- The button opens a wizard to choose month/year and then processes logs in chronological order using the existing `action_sync_hr_attendance()` logic.
