# Simple continuous Attendance boundary workflow

Baseline: `t4tek_entry_control_time_display_simple_module_offset_fixed.zip`.

## What changed

When the Create Attendances button or the daily cron processes Attendance Logs, the module now uses a simpler continuous-log rule:

1. Attendance Logs remain the source of truth.
2. Existing Attendance Logs are not deleted or rebuilt.
3. Directions are kept continuous by employee: Check In -> Check Out -> Check In -> Check Out.
4. For a completed module-local day, if the last log of that day is Check In, the module creates the missing boundary logs if they do not already exist:
   - 23:59 Check Out on that day.
   - 00:00 Check In on the next day.
5. The 00:00 carry-over Check In is always created together with the 23:59 Check Out so the next day remains continuous. The next real log can then become the matching Check Out when appropriate.
6. The module still does not create future boundary logs for the current or future module-local day.

## Timezone behavior

System-generated logs keep `device_timezone = 0`.
Their `check_time` is calculated using the module timezone, default `Asia/Ho_Chi_Minh`.

