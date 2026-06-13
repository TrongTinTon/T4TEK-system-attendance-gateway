# 2026-06-13 - Processing Ledger: one row per Controller

## Changed

- `entry.control.attendance.cron.run` is now treated as a Controller-level snapshot.
- Each Controller keeps only one Processing Ledger row.
- `business_date` now represents the current/last processed business date for that Controller.
- The cron updates the existing Controller ledger row instead of creating one row per Controller/day.
- Legacy per-day rows are collapsed during module initialization and during cron access.

## Runtime behavior

```text
Controller A due for business date 2026-06-12
→ use/update Controller A ledger row
→ mark running
→ process attendance
→ mark done with business_date = 2026-06-12

Next day Controller A due for business date 2026-06-13
→ reuse the same Controller A ledger row
→ reset counters/status
→ process attendance
→ update business_date = 2026-06-13
```

## Reason

This keeps the Processing Ledger screen clean and avoids unbounded growth where every Controller creates one new ledger row per day.
