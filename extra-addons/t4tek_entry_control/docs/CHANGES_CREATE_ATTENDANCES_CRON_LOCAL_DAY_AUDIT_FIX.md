# Create Attendances / Cron local-day audit fix

Version: 19.0.30.62

Baseline reset source: `t4tek_entry_control_utc_device_timezone_canonical_reset.zip`.

## Confirmed canonical storage

- Controller sends `2026-05-27 10:02:38+07`.
- Attendance Log stores `check_time = 2026-05-27 03:02:38` as Odoo UTC-naive.
- Attendance Log stores `device_timezone = +07:00`.
- Business day grouping is based on Device Local Time derived from `check_time + device_timezone`, not raw UTC date.

## Fix

`Create Attendances` and `Entry Control: Create Daily Attendances` now refresh/resequence employee logs while rebuilding system-generated boundary logs day by day.

This avoids a bug where adding a system 23:59 Check Out for one day changes the expected direction of the next day, but the old in-memory log set still treats the next real Check In as Check Out.

## Expected behavior

- Missing daily checkout creates system `23:59 Check Out` in Attendance Logs.
- If the next local day has no real log, system `00:00 Check In` is also created in Attendance Logs.
- If the next local day has a real log, no redundant `00:00 Check In` is created.
- `hr.attendance` is created only from closed pairs and never left open.
- Cron and manual button use the same calculation logic.
