# Attendance Create/Cron Audit Fix

- Restrict hr.attendance creation to the requested wizard/cron business days.
- Cron demo mode processes yesterday and today every minute.
- Do not update arbitrary/manual Odoo attendances; update only Entry Control managed or linked rows.
- Remove duplicate Entry Control managed attendance rows for the same employee/day.
- Do not create the next-day 00:00 system log when the next day already has real Attendance Logs.
- Keep 23:59/00:00 boundary records in Attendance Logs only; never leave an open hr.attendance.
