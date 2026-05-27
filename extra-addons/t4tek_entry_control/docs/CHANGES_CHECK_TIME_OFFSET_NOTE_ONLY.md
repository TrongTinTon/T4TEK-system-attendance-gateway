# Check Time offset suffix is note-only

Version: 19.0.30.53

- Controller value `2026-05-27 08:41:26+07` is stored in Attendance Logs as `check_time = 2026-05-27 08:41:26`.
- `+07` is stored separately as `device_timezone = +07:00` only for audit/context.
- No UTC conversion is applied to Attendance Logs Check Time.
- System-generated Attendance Logs use the same rule:
  - `23:59 Check Out` is stored as `23:59`
  - `00:00 Check In` is stored as `00:00`
  - `device_timezone` is copied from the source real log as a note.
- Attendance Logs UI uses the non-stored display field labelled `Check Time` so Odoo web does not add the user timezone a second time.
