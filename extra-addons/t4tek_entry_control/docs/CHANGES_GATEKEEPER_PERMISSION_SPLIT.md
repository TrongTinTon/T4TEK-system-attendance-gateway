# Gatekeeper Permission Split

This build separates Gatekeeper application permissions from Odoo Settings/System Administrator permissions.

## Groups

1. **Gatekeeper User**
   - Read-only access to Devices, Employee Sync Status, and Attendance Logs.
   - No access to Controllers, Secret Keys, or Settings menus.

2. **Gatekeeper Manager**
   - Includes Gatekeeper User.
   - Can manage operational Gatekeeper records and run **Create Attendances**.
   - Cannot access Controllers, Secret Keys, or Gatekeeper Settings.

3. **Gatekeeper Administrator**
   - Includes Gatekeeper Manager.
   - Full Gatekeeper administration: Controllers, Secret Keys, Settings, Devices, Employee Sync Status, Attendance Logs.
   - Does **not** imply `base.group_system`, so assigning this group no longer makes the user an Odoo Settings/System Administrator.

## Important upgrade note

Older builds made `Gatekeeper Administrator` imply `base.group_system`. This build clears that implied group in `security/groups.xml`. After upgrading the module, review existing users and remove the Odoo **Settings** permission manually if it was previously granted directly or retained by Odoo from an older assignment.
