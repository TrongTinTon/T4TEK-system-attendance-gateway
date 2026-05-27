# 19.0.30.46 - Check Time single field / device-local storage

- Removed display/helper fields from Attendance Logs UI/model usage:
  - `check_time_local`
  - `device_check_time`
  - `device_timezone`
- Attendance Logs now use only one field: `check_time` with label `Check Time`.
- Controller timestamps with timezone offsets are preserved as device clock time.
  - Example: `2026-05-27 07:47:06+07` is stored/displayed as `2026-05-27 07:47:06`.
- Synthetic system logs `23:59 Check Out` and `00:00 Check In` are also stored in the same device-local clock convention.
- Create Attendances and cron continue to calculate from Attendance Logs only.
