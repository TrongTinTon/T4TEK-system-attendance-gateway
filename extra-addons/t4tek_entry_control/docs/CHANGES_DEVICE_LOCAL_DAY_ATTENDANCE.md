Device Local Day attendance calculation
======================================

- Keep `check_time` stored using Odoo UTC-naive Datetime semantics.
- Keep `device_timezone` as the device timezone context, for example `+07:00`.
- Create Attendances and cron now calculate business days by converting each Attendance Log from UTC storage to Device Local Time using `device_timezone`.
- Wizard/Cron search a broad UTC window first, then filter target days by Device Local Day.
- System-generated 23:59 Check Out / 00:00 Check In are created from local device boundaries and stored back as UTC, so Odoo UI displays the intended local time.
