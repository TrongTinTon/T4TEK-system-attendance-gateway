# Time display = visible Check Time + effective timezone

- `time_display` now follows the UI requirement: **Time = visible Check Time + effective timezone offset**.
- Real logs add the offset from `device_timezone`, for example `+07:00` adds 7 hours.
- System-generated logs keep `device_timezone = 0`; this marker adds 0 hours so system rows remain 23:59 / 00:00 on UI.
- If a real log has no valid timezone note, the module timezone configuration (`entry_control.attendance_timezone`, default `Asia/Ho_Chi_Minh`) is used as fallback.
- The field remains a computed Char so Odoo will not apply user timezone conversion again to the displayed value.
