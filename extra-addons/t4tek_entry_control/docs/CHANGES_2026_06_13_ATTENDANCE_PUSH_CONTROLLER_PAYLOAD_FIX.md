# Attendance Push Controller Payload Compatibility Fix

Date: 2026-06-13

## What was verified in Controller

The Controller sends Attendance Logs to:

`POST /api/entry_control/v1/attendance/logs/push`

Payload shape:

```json
{
  "controller_uid": "<controller_code>",
  "controller_id": "<controller_code>",
  "odoo_database": "<database>",
  "logs": [
    {
      "id": 123,
      "local_id": 123,
      "device_id": 1,
      "serial_number": "<device_serial>",
      "employee_id": "<device_enroll_number>",
      "check_time": "yyyy-MM-dd HH:mm:ss",
      "device_timezone": "+07:00",
      "check_type": "0",
      "verify_type": "1",
      "push_status": "pending",
      "error_message": null
    }
  ]
}
```

## Fixes

- Store the raw Controller local attendance log id in `controller_local_id`.
- Return `local_id` and `id` in each API result so the Controller can mark local logs as pushed successfully.
- Keep `attendance_log_id` / `server_attendance_log_id` for the Odoo log id.
- Improve duplicate detection for unknown employees by including raw `employee_code_controller`.
- Add optional UI field `Controller Local ID` to Attendance Logs for troubleshooting.
