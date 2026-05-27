# Cron disabled by default

- The scheduled action `Entry Control: Create Daily Attendances` is now installed and upgraded with `active = False`.
- The immediate `ir.cron.trigger` record was removed from the XML data file so the module will not run attendance creation automatically right after install/upgrade.
- Admin can enable or run the cron manually later from Odoo Scheduled Actions when needed.
- Manual Create Attendances button behavior is unchanged.
