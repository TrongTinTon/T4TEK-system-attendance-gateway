# Auto Daily Attendance Cron

Added a built-in Odoo scheduled action:

- Name: Entry Control: Create Daily Attendances
- Model: entry.control.attendance.log
- Method: cron_create_daily_attendances()
- Frequency: Daily
- Default processing date: yesterday

The cron creates/updates hr.attendance using the existing derived daily logic:

- Attendance Logs remain unchanged for audit.
- check_in is derived from the first Check In log of the day.
- check_out is derived from the final raw log after check_in when at least two logs exist.
- API ingest still does not auto-create hr.attendance.
- The list-view Create Attendances button remains available for manual/demo processing.
