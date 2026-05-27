# Check Time ingest strict debug

- Attendance Log `check_time` remains the device/controller wall-clock time.
- `2026-05-27 09:12:05+07` is stored as `2026-05-27 09:12:05`; `+07` is stored only in `device_timezone`.
- The API response for attendance log push now returns `check_time_stored`, `check_time_display`, and `device_timezone` so controller-side logs can confirm what Odoo stored.
- `_safe_datetime_value()` no longer converts offset timestamps to UTC for compatibility with legacy call paths.
