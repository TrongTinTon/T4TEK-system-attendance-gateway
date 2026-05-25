# Device Serial Number Identifier

## Changed

- `entry.control.device` now uses `serial_number` as the canonical display/name field (`_rec_name`).
- Device upsert searches by global Serial Number instead of `(controller_id, serial_number)`. If a physical device moves to another Controller, the existing row is updated instead of creating a duplicate.
- Device IP is stored only as `ip_address` / `Last IP Address` for diagnostics. It is not used as identity.
- `/api/entry_control/v1/devices/report` rejects device rows that do not provide a Serial Number.
- `entry.control.attendance.log` stores the device serial for display; API payloads must use `serial_number` only.
- Attendance log ingestion links/creates devices by Serial Number and deduplicates logs by Serial Number, not IP or device display name.

## Reason

IP address can overlap between different sites/networks or change over time. Serial Number is the stable physical-device identifier and should be the value shown in Attendance Logs.


## Strict API contract update

- Device report and attendance push now accept only `serial_number` for device identity.
- Removed transport aliases such as `serial_number`, `serialNumber`, `sn`, and `device_code` from the API contract.
