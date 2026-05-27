# Time display uses module timezone canonically

## Fixed

- `time_display` no longer adds `device_timezone` on top of the visible Odoo `check_time`.
- Controller timestamps such as `2026-05-27 10:02:38+07` are treated as already carrying the device/local offset.
- The canonical storage remains Odoo UTC-naive:
  - input: `2026-05-27 10:02:38+07`
  - stored `check_time`: `2026-05-27 03:02:38`
  - displayed `Time` with module timezone `Asia/Ho_Chi_Minh`: `2026-05-27 10:02:38`
- `device_timezone` is kept as audit/context only and is not added again for the `Time` column.
- Added a diagnostic warning if a real log's `device_timezone` offset does not match the configured module timezone offset.
