# 19.0.30.26 - Daily Attendance Cron with Scheduled Actions Trigger

- Keeps the existing daily scheduled action: `Entry Control: Create Daily Attendances`.
- Adds an `ir.cron.trigger` record so the cron is queued immediately after module install/update.
- Sets `nextcall` explicitly so the scheduled action is visible/due in Odoo Scheduled Actions.
- Writes diagnostic parameters after each run:
  - `entry_control.last_daily_attendance_cron_at`
  - `entry_control.last_daily_attendance_cron_date`
  - `entry_control.last_daily_attendance_cron_log_count`
- Does not change Attendance Logs directions.
- API log ingest still does not auto-create `hr.attendance`.
