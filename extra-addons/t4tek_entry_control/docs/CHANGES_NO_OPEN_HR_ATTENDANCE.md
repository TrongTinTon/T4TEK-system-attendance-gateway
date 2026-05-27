# 19.0.30.43 - Do not create open hr.attendance

- Attendance Logs remain the source of truth.
- Synthetic 23:59 Check Out and 00:00 next-day Check In are stored only in Attendance Logs.
- `hr.attendance` is created/updated only when both Check In and Check Out exist for the business day.
- Existing stale open Entry Control attendance rows are removed before recalculation to avoid Odoo errors like “employee hasn’t checked out”.
- Button Create Attendances and cron both use this same logic.
