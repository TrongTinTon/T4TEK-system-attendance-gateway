# 19.0.30.13 - Odoo UI and Attendance Log cleanup

- Generate Key now reloads the Controller form so the new Secret Key is filled into the input immediately.
- Employee Sync Status no longer stores/displays Device Password/PIN.
- Attendance Logs no longer store/display PIN.
- Removed Direction Source and Device Direction from Attendance Logs; only the final Direction remains visible/stored.
- Removed duplicated Device Check Type; only Check Type remains.
- Removed Event Hash storage and unique event-hash constraint; duplicate detection now uses controller/device/employee/check time/check type/verify type.
