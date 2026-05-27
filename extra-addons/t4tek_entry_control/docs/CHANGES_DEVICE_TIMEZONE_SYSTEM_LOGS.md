Device timezone and system log time handling
============================================

- Attendance Logs now keep a `device_timezone` field parsed from the Controller `check_time` payload, for example `+07:00`.
- System-generated Attendance Logs inherit the source log device timezone.
- 23:59 Check Out and 00:00 Check In system rows are generated as device-local wall-clock times, not shifted by Odoo/user timezone conversions.
- The single operational Check Time field remains the source used by Create Attendances and the cron.
