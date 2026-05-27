# Time Display Simple Module Offset Fix

- Attendance Logs `Time` now follows the simple UI rule requested by user: real device logs display Check Time plus the Entry Control module timezone offset.
- System-generated logs keep canonical module-time display so 23:59 and 00:00 boundary rows remain stable.
- No database rows are deleted or rebuilt.
- Module timezone default remains `Asia/Ho_Chi_Minh`.
