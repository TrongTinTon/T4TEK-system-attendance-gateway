# Fix duplicate timezone config on module upgrade

Problem:
- Directly creating `ir.config_parameter` with key `entry_control.attendance_timezone` can fail on upgrade when the key already exists.
- PostgreSQL raises `ir_config_parameter_key_uniq` duplicate key violation.

Fix:
- Removed `data/settings_data.xml` from manifest data loading.
- Kept module timezone default in Python fallback: `Asia/Ho_Chi_Minh`.
- Settings screen continues to save the key using `ir.config_parameter.set_param()`, which updates safely instead of creating a duplicate record.

Result:
- Upgrade no longer fails when `entry_control.attendance_timezone` already exists.
- Fresh install still uses `Asia/Ho_Chi_Minh` by default.
