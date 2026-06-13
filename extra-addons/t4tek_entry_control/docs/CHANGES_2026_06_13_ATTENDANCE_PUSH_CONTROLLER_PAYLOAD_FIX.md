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

- Echo the raw Controller local attendance log id in the API response as `local_id` / `id` for push acknowledgement.
- Return `local_id` and `id` in each API result so the Controller can mark local logs as pushed successfully.
- Keep `attendance_log_id` / `server_attendance_log_id` for the Odoo log id.
- Improve duplicate detection for unknown employees by including raw `employee_code_controller`.
- Later UI cleanup removes Controller Local ID from Attendance Logs; it is not stored as Odoo audit data.
