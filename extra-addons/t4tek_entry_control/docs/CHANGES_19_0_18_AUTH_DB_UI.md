# T4TEK Entry Control - Auth, DB, Status UI Cleanup

## Scope
This package was rebuilt from the fresh uploaded `t4tek_entry_control.zip` source only.

## Authentication
- `/api/entry_control/v1/auth/token` now authenticates with an Odoo user account before issuing Controller tokens.
- Request payload must include `controller_code`, `odoo_login`, and `odoo_password`.
- Response returns access token and refresh token metadata.
- `/api/entry_control/v1/auth/refresh` rotates tokens using the refresh token.
- Stored tokens are hashed; only token hints/expiry dates are stored for operators.

## Database/model cleanup
- Removed unused legacy Odoo models/views from the active module package: command, event, conflict, token wizard, employee generate wizard, and legacy entry_control files.
- Removed `raw_data` from Attendance Logs. Parsed/queryable fields are kept instead: controller, device, PIN, check time, UTC/raw/timezone, verify method, status, message, and linked `hr.attendance`.
- Fingerprint pending review is handled directly in Fingerprint Master; the obsolete Sync Conflict model is no longer used.

## Operator UI
- Controller list/form now shows operational state, online/offline/error device counts, token expiry, auth user, block/unblock actions, and last error.
- Device list/form now shows operational state, connection status, sync timestamps, and last error.
