# Action Create Attendances - Completed Business Days

- Aligns manual Create Attendances with the module timezone used by cron.
- Processes only completed business days, preventing the wizard from creating 23:59 / 00:00 system boundary logs for the current open day.
- Keeps DB queries in UTC-naive ranges via `_local_day_utc_bounds()`.
- Adds created/updated/skipped/failed counters to the completion notification.
