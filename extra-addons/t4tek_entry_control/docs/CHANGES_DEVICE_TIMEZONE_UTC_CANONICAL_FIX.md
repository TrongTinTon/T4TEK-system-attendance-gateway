# 19.0.30.50 - Device timezone canonical Check Time fix

- Store Attendance Log `check_time` as Odoo UTC-naive datetime again.
- Preserve `device_timezone` from Controller payload, e.g. `+07:00`.
- Parse `2026-05-27 08:13:27+07` as UTC storage `2026-05-27 01:13:27` and keep `device_timezone = +07:00`.
- System-generated logs now use the source log device timezone:
  - local `23:59 Check Out` in `+07:00` is stored as `16:59 UTC`
  - local `00:00 Check In` in `+07:00` is stored as `17:00 UTC` on the previous UTC date
- This prevents UI drift such as `23:59 -> 06:59` and `00:00 -> 07:00` when Odoo users are in Vietnam timezone.
- Attendance Logs remain the source of truth and `hr.attendance` is still calculated only from Attendance Logs.
