# Gatekeeper Cron Run UTC/Local Display

- Split the Settings diagnostic `Last Cron Run` into two explicit fields:
  - `Last Cron Run UTC` for the UTC-naive Odoo/server timestamp.
  - `Last Cron Run Local` for the same timestamp displayed in the configured Module Timezone.
- Kept the legacy `entry_control.last_daily_attendance_cron_at` config key for upgrade compatibility.
- Added backward-compatible fallback so older stored UTC values still display after module upgrade.
