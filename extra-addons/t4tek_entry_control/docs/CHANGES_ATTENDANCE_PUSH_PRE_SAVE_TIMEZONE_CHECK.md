# Attendance push pre-save timezone check

- Hardened `/api/entry_control/v1/attendance/logs/push`.
- The API now normalizes controller `check_time` before calling model ingest.
- `2026-05-27 09:12:05+07` is saved as `2026-05-27 09:12:05`; `+07` is stored only as `device_timezone`.
- API response includes `pre_save_timezone_check` and `timezone_validation_ok` for demo/debug.
