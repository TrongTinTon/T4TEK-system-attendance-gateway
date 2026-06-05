# Controller Timezone + Per-Controller Daily Cron

Date: 2026-06-05

## What changed

1. Added `Controller Timezone` on `entry.control.controller`.
   - Every Controller has its own IANA timezone, for example `Asia/Ho_Chi_Minh`.
   - All devices under that Controller inherit this timezone.
   - The global Settings timezone is now only a default/fallback for new Controllers or legacy records.

2. Server APIs now return Controller timezone configuration.
   - `/api/entry_control/v1/auth/token`
   - `/api/entry_control/v1/auth/refresh`
   - `/api/entry_control/v1/hello`

   Response fields include:

   ```json
   {
     "controller_timezone": "Asia/Ho_Chi_Minh",
     "controller_timezone_offset": "+07:00",
     "device_timezone_offset": "+07:00"
   }
   ```

3. Daily cron no longer uses one module-wide timezone for all logs.
   - Cron runs when Odoo Scheduled Action `Next Execution Date` is due.
   - After cron starts, it processes each active Controller separately.
   - Each Controller calculates its own `yesterday` and UTC DB range using its configured timezone.

4. System-generated 23:59 Check Out and 00:00 Check In logs now use the source Controller timezone.

5. Manual `Create Attendances` also processes by Controller timezone.

## Operational note

Odoo stores Scheduled Action `nextcall` as UTC internally and displays it through the Odoo UI using the current user's timezone. To make the cron run at a Vietnam local time such as 00:15, set the administrator/user timezone to `Asia/Ho_Chi_Minh`, then set `Next Execution Date` to `00:15` in the Scheduled Actions UI.
