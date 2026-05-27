# Continuous boundary logs: create for selected processing window

- Removed the guard that skipped the current module-local day.
- Create Attendances / cron now uses the simple rule: if the last Attendance Log of a processed day is Check In, create 23:59 Check Out and 00:00 Check In using find-or-create.
- No Attendance Logs are deleted or rebuilt.
- System logs keep device_timezone = 0 and use module timezone for canonical boundary time.
