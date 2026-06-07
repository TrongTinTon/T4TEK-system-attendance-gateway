# Groups upgrade serialization fix

Fixes upgrade failures caused by PostgreSQL `SerializationFailure: could not serialize access due to concurrent update` while loading `security/groups.xml`.

## Change
- Wrapped stable Gatekeeper group/category records in `<data noupdate="1">`.
- This prevents unnecessary writes to `res.groups` during module upgrade.
- Fresh installs still create the groups normally.

## Operational note
If the server is already in a failed/partial upgrade transaction, restart Odoo and retry the upgrade once. For safest upgrade, stop background jobs/controllers temporarily or run the module update with a single Odoo worker.
