# 19.0.19 Employee auto Device User + User Device Sync Status

- Module depends on `hr` and `hr_attendance`, so Employee is installed when installing T4TEK Attendance Gateway.
- Added `post_init_hook` to mirror existing Employees with unique PIN into Device Users. Blank or duplicate PINs are skipped and logged.
- Employee create/write automatically creates/updates the matching Device User.
- Employee archive disables the Device User.
- Employee delete marks Device User as `is_deleted=True` and `is_active=False` so Controllers can still pull a delete desired state.
- Added `entry.control.user.device.status` to show on which Controller/device each PIN has been synchronized, including success/failed/error message.
- Added `/api/entry_control/v1/sync/user-device/results` for Controller result reporting.
- Deprecated Odoo Command Pull routes were removed from the module. Desired-state manifest is the only server-to-controller workflow.
