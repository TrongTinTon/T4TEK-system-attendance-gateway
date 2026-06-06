# Device report controller reassignment fix

## Problem
When a physical device was moved from one Controller to another, Odoo could still show the old Controller. A stale offline report from the old Controller could overwrite the device ownership after the new Controller had been configured.

## Fix
Device identity remains `serial_number`, but Odoo now applies a cross-controller ownership rule:

- If the reporting Controller sends an `online` device report, the device is reassigned to that Controller.
- If a different Controller sends only an `offline` or `deactive` stale report, Odoo ignores that report for ownership and status updates.
- If an offline report contains a newer `last_online_at` than the current Odoo record, Odoo accepts it as a newer ownership signal.

This prevents old Controllers from moving a device back after it has been handed over to a new Controller.
