# Check Time debug columns

Version: 19.0.30.55

Changes:
- Attendance Logs UI shows `Check Time Stored`, the actual stored `check_time` value formatted without timezone conversion.
- Attendance Logs UI shows `Check Time Display`, the UI/debug display value.
- The original Odoo Datetime field `check_time` is available as optional `Check Time (Odoo Datetime)` to compare Odoo web-client timezone behavior.
- Controller form > Attendance Logs tab shows the same debug columns.
