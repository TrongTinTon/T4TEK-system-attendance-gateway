# Next-day Attendance Logs remain source of truth

- `hr.attendance` remains derived data only.
- When a day is closed by generated `23:59` checkout, the module creates a next-day `00:00` placeholder only if the next day has no real Attendance Logs yet.
- If the next day already has Attendance Logs, no `00:00` placeholder is created.
- If a previous cron run already created a `00:00` placeholder, processing the next day will overwrite it using the first real Check In from Attendance Logs.
