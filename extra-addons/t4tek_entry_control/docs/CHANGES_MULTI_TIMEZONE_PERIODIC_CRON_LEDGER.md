# Gatekeeper Multi-Timezone Periodic Cron + Processing Ledger

## Goal

Implement a scheduler design where Odoo cron is only a periodic UTC trigger, while business days are calculated per Controller timezone.

## Design implemented

- Odoo Scheduled Action runs periodically in UTC, default interval: every 15 minutes.
- Each Controller has its own `attendance_timezone` using IANA timezone names, for example `Asia/Ho_Chi_Minh` or `America/Los_Angeles`.
- Attendance Logs keep Odoo-standard UTC-naive `check_time` values.
- Business day boundaries are calculated in the Controller timezone, then converted to UTC for DB queries.
- System-generated `23:59:59 Check Out` and `00:00:00 Check In` logs are created in Controller local time and stored as UTC-naive values.
- A new processing ledger model prevents duplicate processing for the same Controller and business date.

## New model

`entry.control.attendance.cron.run`

Key fields:

- `controller_id`
- `business_date`
- `timezone`
- `local_run_time`
- `due_at_utc`
- `status`: `pending`, `running`, `done`, `failed`
- metrics: `employee_count`, `log_count`, `created_count`, `updated_count`, `skipped_count`, `failed_count`

SQL guard:

```sql
unique(controller_id, business_date)
```

## Runtime behavior

Every cron tick:

1. Get `now_utc`.
2. Loop through active/non-blocked Controllers.
3. Convert `now_utc` to each Controller's `attendance_timezone`.
4. Compare Controller local time with `Daily Local Processing Time` from Gatekeeper Settings. Default: `00:00`.
5. If due, process yesterday according to that Controller timezone.
6. Check ledger. If `controller_id + business_date` is already `done`, skip.
7. Mark ledger `running`, process attendance, then mark `done`. If an exception occurs, mark `failed` for retry.

## Configuration

Gatekeeper Settings adds:

- `Daily Local Processing Time`, default `00:00`, format `HH:MM`.

Example:

- Cron interval: every 15 minutes.
- Daily Local Processing Time: `00:00`.
- VN Controller: process when VN local time reaches `00:00`.
- US Controller: process when US local time reaches `00:00`.

## Scheduled Action

`Gatekeeper: Create Daily Attendances`

- interval: 15 minutes
- active: False by default for safe upgrades

Enable it after upgrade when ready.
