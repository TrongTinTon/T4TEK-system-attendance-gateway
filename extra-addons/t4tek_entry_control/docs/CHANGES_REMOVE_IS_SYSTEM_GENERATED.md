# Remove is_system_generated

- Removed `is_system_generated` field from Attendance Logs.
- System-created Attendance Logs are identified only by `verify_method = system_generated`.
- Upgrade cleanup drops the old `is_system_generated` column if it exists.
