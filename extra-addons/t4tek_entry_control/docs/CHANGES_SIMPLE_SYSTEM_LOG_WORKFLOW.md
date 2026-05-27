# Simple system-generated Attendance Log workflow

- Do not delete/rebuild existing system-generated Attendance Logs on every Create Attendances/Cron run.
- Only create a missing 23:59 Check Out for a completed business day whose last log is Check In.
- Only create the next-day 00:00 Check In when the next business day has no real device log yet.
- Never create 23:59/00:00 for the current or future business day.
- System-generated logs keep `device_timezone = 0`; `check_time` is calculated from the module timezone setting.
- The Time column is a Char computed from UTC-naive `check_time` into `entry_control.attendance_timezone`; Odoo user timezone and device_timezone are not added again.
