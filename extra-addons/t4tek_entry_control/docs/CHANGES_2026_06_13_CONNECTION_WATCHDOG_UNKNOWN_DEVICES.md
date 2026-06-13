# 2026-06-13 - Connection Watchdog: Controller Offline + Device Unknown

## What changed

Added a server-side scheduled action:

- **Gatekeeper: Check Connection Status**
- Runs every 1 minute by default
- Calls `entry.control.controller.cron_check_connection_status()`

## Behavior

- If a Controller heartbeat is stale beyond `entry_control.controller_heartbeat_timeout_seconds` (default: 300 seconds):
  - Controller status becomes `offline`
  - Devices under that Controller become `unknown`

- If the Controller is still alive and reports a physical Device disconnect through `/api/entry_control/v1/devices/report`:
  - Device status remains `offline`

## Reason

This separates two different conditions:

- `offline`: the Controller is alive and confirms the physical Device is unreachable
- `unknown`: Odoo lost contact with the Controller, so the physical Device state cannot be trusted

## UI / Settings

- Device status now supports `unknown`
- Device list/form badge decorations include `unknown`
- Gatekeeper Settings includes **Controller Heartbeat Timeout (seconds)**
