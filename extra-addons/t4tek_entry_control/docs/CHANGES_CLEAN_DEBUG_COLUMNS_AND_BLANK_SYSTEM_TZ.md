# Clean debug timezone columns and blank system Device Timezone

- Removed the debug-only Module Time Now / Module Timezone columns from Attendance Logs and Controller attendance-log lists/forms.
- System-generated Attendance Logs now leave Device Timezone empty instead of showing `0`.
- Existing system-generated rows with Device Timezone `0`, `0:00`, or `00:00` are normalized to empty during module upgrade.
- Boundary time calculations still use the module timezone setting internally, so 23:59 / 00:00 system logs continue to display correctly.
- Cron remains disabled by default; manual Create Attendances is unchanged.
