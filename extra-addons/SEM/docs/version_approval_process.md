# Quy trình duyệt phiên bản HR Employee trong SEM

## Mục tiêu
- Thêm nút `Duyệt phiên bản` trên form `hr.employee` trong module SEM.
- Khi duyệt phiên bản, đánh dấu phiên bản HR employee (`hr.version`) là đã duyệt.
- Khóa các trường dữ liệu liên quan đến version đã duyệt để không sửa được.
- Giữ nguyên luồng tạo phiên bản qua widget `versions_timeline` của Odoo.

## Các bước cài đặt

### 1. Mở rộng model `hr.version`
- File: `SEM/models/hr_version_inherit.py`
- Thêm các trường:
  - `is_approved` (Boolean)
  - `approved_by_id` (Many2one `res.users`)
  - `approved_date` (Datetime)
- Thêm method `action_approve()` để gán trạng thái duyệt và thông tin người duyệt.
- Ghi đè `write()` để chặn cập nhật khi phiên bản đã duyệt:
  - Nếu `is_approved` đã true và cố gắng thay đổi các giá trị khác, raise `UserError`.

### 2. Mở rộng model `hr.employee`
- File: `SEM/models/sem_employee_inherit.py`
- Khai báo field `version_is_approved` liên kết tới `version_id.is_approved`.
- Thêm method `action_approve_current_version()` để gọi `version_id.action_approve()` và reload form.
- Giữ nguyên `related` field để hiển thị trạng thái duyệt trong view.

### 3. Chỉnh sửa view employee SEM
- File: `SEM/views/sem_employee_views.xml`
- Thêm field ẩn `<field name="version_is_approved" invisible="1"/>` để dùng điều kiện hiển thị.
- Thêm nút `Duyệt phiên bản` trong `header`:
  - `type="action"`
  - `name="%(SEM.action_approve_current_version)d"`
  - `invisible="version_is_approved"`
- Thêm nút trạng thái `Phiên bản đã duyệt` hiển thị khi `version_is_approved` true.
- Tránh dùng `attrs` và `states` trên Odoo 17+ vì đã không còn hỗ trợ.

## Vấn đề gặp phải và cách giải quyết

### 1. Lỗi parse khi nạp view
- Lỗi: `ParseError ... Kể từ phiên bản 17.0, các thuộc tính "attrs" và "states" không còn được sử dụng.`
- Nguyên nhân: trong view vẫn để `attrs="{'readonly': [('version_is_approved', '=', True)]}"`.
- Giải pháp: xóa `attrs` và dùng `readonly` trực tiếp trên từng field, nhóm hay button nếu cần.

### 2. Lỗi `return` ngoài function trong `ir.actions.server`
- Khi dùng action server trực tiếp, code Python cần gán `action = {...}` thay vì `return {...}` trong XML.
- Tuy nhiên cuối cùng giải pháp tốt hơn là chuyển nút vào method object trên model thay vì action server.

### 3. Không hiển thị thay đổi sau upgrade
- Kiểm tra:
  - module SEM đã được upgrade đúng không
  - view sử dụng có phải `view_employee_form_t4tek` không
  - có view khác override cùng form hay không
- Trong Odoo, method object trên `hr.employee` có thể chạy nhưng view dùng không đúng template thì sẽ không thấy.

## File chính đã sửa
- `SEM/models/hr_version_inherit.py`
- `SEM/models/sem_employee_inherit.py`
- `SEM/views/sem_employee_views.xml`
- `SEM/__manifest__.py` (đảm bảo view được load nếu cần)

## Lưu ý triển khai
- Nên restart Odoo và clean cache trình duyệt sau khi nâng cấp module.
- Nếu vẫn không thấy, cần kiểm tra view hiện tại trong UI đang dùng view ID nào hoặc có module khác ghi đè view.
- Với các trường version derived từ `version_id`, dùng `related` trực tiếp thay vì tự tính toán lưu trữ phức tạp.

## Kết luận
Quy trình này mở rộng luồng HR version mặc định của Odoo để thêm chức năng duyệt và khóa dữ liệu. Quan trọng nhất là:
- giữ logic kiểm soát trong backend `hr.version`
- dùng `related` field để hiển thị trạng thái duyệt
- tránh dùng `attrs/states` trong XML Odoo 17+
- xác nhận form đúng được load bởi view SEM.
