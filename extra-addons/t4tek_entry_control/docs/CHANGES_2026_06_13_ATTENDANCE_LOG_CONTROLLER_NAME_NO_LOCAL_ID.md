# Attendance Logs: Controller Name only, no Controller Local ID storage

## Changes

- Attendance Log UI now shows `Controller Name` instead of the Controller many2one field.
- Removed `Controller Local Log ID` from `entry.control.attendance.log` model and views.
- Attendance push API still echoes the incoming `local_id` as `local_id` and `id` so the Controller can mark local logs as pushed successfully.
- Odoo no longer stores the Controller local attendance log id in Attendance Logs.

## Reason

The local Controller log id is only needed for the Controller push acknowledgement. It is not needed as an Odoo audit column.
