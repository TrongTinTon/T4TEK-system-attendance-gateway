# Device Offline Time Report Fix

This build separates actual device status timestamps from Odoo report receive time.

## Fixed

- Controller local DB now tracks `last_online_at`, `last_offline_at`, and `last_status_changed_at`.
- `last_offline_at` is set only when the device first transitions into the current offline period; it is not refreshed on every status poll.
- Device report payload now includes actual status timestamps from the Controller.
- Odoo `entry.control.device` now stores actual last online/offline/status-change times and a separate `last_reported_at` audit timestamp.
- Odoo no longer overwrites `last_seen_at` with server receive time for offline reports.

## Rule

`last_reported_at` = when Odoo received the payload.
`last_online_at` = when Controller actually saw device online.
`last_offline_at` = when Controller first detected current offline period.
`last_status_changed_at` = when Controller status changed online/offline.
