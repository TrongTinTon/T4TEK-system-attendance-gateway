# Server-owned alternating direction

- API still stores raw Attendance Logs only; it does not auto-create `hr.attendance`.
- Device/controller `check_type` / AttState is stored as raw data only.
- Operational `direction` is decided by Odoo server:
  - if the previous log for the employee is `Check In`, the next log becomes `Check Out`;
  - otherwise the next log becomes `Check In`.
- `Create Attendances` recomputes directions for the selected month/year in chronological order before calling the existing attendance creation logic.
