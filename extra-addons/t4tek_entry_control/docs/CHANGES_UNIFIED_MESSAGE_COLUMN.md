# 19.0.30.42 - Unified Message column

- Attendance Logs UI now shows only one user-facing `Message` column.
- `Error Message` remains technical/internal but is no longer shown as a separate column on Attendance Logs.
- Failed attendance calculation writes the error text into `message` as the unified display column.
- System-generated Attendance Logs now show the short message: `Hệ thống tự tạo`.
- hr.attendance message is shortened to `Hệ thống tự tạo` when generated boundary logs are involved, otherwise `Tính từ Attendance Logs`.
