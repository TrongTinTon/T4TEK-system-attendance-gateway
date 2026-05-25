# Clean Controller / Employee / Attendance refactor

- Rebuilt Odoo module around Controllers, Devices, Employee Sync Status, and Attendance Logs.
- Removed Odoo command pull, Incoming Events, Sync Conflicts, and server-side user-device sync status.
- Added Controller ID + Secret Key token authentication and refresh token API.
- Added POST employee delta API and employee sync-status report API.
- Kept Attendance Direction Inference for hr.attendance creation/update.
