# Gatekeeper Settings Timezone Selection Default

- Changed `entry.control.settings.attendance_timezone` from free text `Char` to Odoo-style `Selection` dropdown.
- The dropdown is populated from the server IANA timezone database.
- Default module timezone is fixed to `Asia/Ho_Chi_Minh`.
- Saved timezone continues to be persisted in `ir.config_parameter` key `entry_control.attendance_timezone`.
- Existing invalid timezone configuration still falls back safely to `Asia/Ho_Chi_Minh`.
