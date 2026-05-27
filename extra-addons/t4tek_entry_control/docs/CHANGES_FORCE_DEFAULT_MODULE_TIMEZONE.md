# Force default module timezone on upgrade

- Adds an upgrade-safe SQL UPSERT for `entry_control.attendance_timezone`.
- If the key is missing, empty, or left as UTC/Etc/UTC/GMT from older builds, it is corrected to `Asia/Ho_Chi_Minh`.
- This avoids the Time column showing UTC while the expected module timezone is Vietnam local time.
- Existing valid custom non-UTC timezone values are preserved.
