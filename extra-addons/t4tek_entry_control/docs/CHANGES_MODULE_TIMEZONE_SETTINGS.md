# Module Timezone Settings

- Added Entry Control > Settings with a Module Timezone field.
- Default timezone is `Asia/Ho_Chi_Minh` when no setting exists.
- The setting is stored in `ir.config_parameter` key `entry_control.attendance_timezone`.
- Attendance Logs now keep only one persisted Check Time field.
- Legacy debug columns `check_time_stored_display`, `check_time_display`, `check_time_db_utc`, and `check_time_device_local` are dropped during module init/upgrade.
- System-generated Attendance Logs store `device_timezone = 0` for UI clarity.
- System-generated 23:59 / 00:00 timestamps are still converted to UTC-naive check_time using the effective business timezone.
- Create Attendances wizard defaults month/year from the module business timezone instead of the current Odoo user's timezone.
- Health API now returns `attendance_timezone` for diagnostics.
