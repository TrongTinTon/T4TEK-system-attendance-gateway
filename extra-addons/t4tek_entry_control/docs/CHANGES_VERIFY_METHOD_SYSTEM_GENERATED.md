# 19.0.30.40 - System Generated verify method

- Added `verify_method = system_generated` / label `System Generated` for synthetic Attendance Logs.
- New system-created 23:59 Check Out and 00:00 Check In logs are identified by `verify_method`, only by `verify_method = system_generated`.
- Removed `is_system_generated` from the model; old database column is dropped during module upgrade.
- Attendance Logs list/search now shows and filters system-generated rows through `Verify Method`.
