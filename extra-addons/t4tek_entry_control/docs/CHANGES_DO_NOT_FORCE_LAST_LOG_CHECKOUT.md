# Do not force final log direction to Check Out

- `Create Attendances` no longer calls `action_recompute_directions()` before creating `hr.attendance`.
- `action_sync_hr_attendance()` now uses existing server-owned Attendance Log directions:
  - first `direction = in` log of the day -> `check_in`
  - last `direction = out` log after check-in -> `check_out`
- If a day has no Check Out log, the generated `hr.attendance` remains open and the final Attendance Log direction is not changed to `out`.
- Raw Attendance Log directions are preserved for audit.
