# 2026-06-13 - Attendance Log chỉ giữ Employee Code Controller

## Yêu cầu

Trong `entry.control.attendance.log`, bỏ lưu và bỏ hiển thị `Employee Code (Server)`.
Chỉ giữ lại `Employee Code (Controller)` để audit đúng mã nhân viên raw mà Controller gửi lên.

## Thay đổi

- Removed field `employee_code_server` from `entry.control.attendance.log`.
- Removed `Employee Code (Server)` from list/form/search views.
- Removed `employee_code_server` from attendance push API response.
- Added DB cleanup to drop legacy column `employee_code_server` during module upgrade.
- Kept `employee_code_controller` as readonly/indexed audit field.
- Kept server-side employee lookup helpers for mapping Controller employee code to `hr.employee`; this is only used for mapping, not stored as a separate Attendance Log field.

## Ghi chú

Sau khi upgrade module, các dữ liệu log cũ vẫn giữ employee mapping qua `employee_id`, nhưng cột legacy `employee_code_server` sẽ bị drop khỏi bảng log.
