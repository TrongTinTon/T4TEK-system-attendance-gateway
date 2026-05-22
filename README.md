# Entry Control - Controller Discovery & Security

## Mục tiêu

Bản nâng cấp này bổ sung cơ chế quản lý controller cho Odoo:

1. Controller tự phát hiện Odoo qua Zeroconf/mDNS.
2. Controller gọi API `controller/hello` để đăng ký IP, port, service name.
3. Odoo lưu controller vào danh sách `Entry Control > Controllers`.
4. Admin duyệt controller trước khi cho phép gửi dữ liệu chấm công.
5. Attendance API chặn controller lạ, controller bị block, token sai, hoặc IP/port không đúng endpoint đã duyệt.
6. Odoo ghi nhận các sự kiện bất thường vào `Entry Control > Security Events`.

## Zeroconf service type đề xuất

- Odoo server advertise: `_odoo-entry-control._tcp.local.`
- Controller advertise: `_entry-controller._tcp.local.`

Controller sau khi tìm thấy Odoo sẽ gọi:

```http
POST /api/entry_control/controller/hello
```

## API đăng ký controller

```http
POST http://ODOO_HOST:8069/api/entry_control/controller/hello
Content-Type: application/json
```

Payload:

```json
{
  "controllerId": "CTRL-GATE-01",
  "controllerName": "Gate Controller 01",
  "ip": "192.168.1.50",
  "apiPort": 5099,
  "serviceName": "CTRL-GATE-01._entry-controller._tcp.local.",
  "serviceType": "_entry-controller._tcp.local.",
  "apiVersion": "1.0",
  "discoverySecret": "optional-shared-secret"
}
```

Response:

```json
{
  "status": "success",
  "message": "Controller discovered. Waiting for approval.",
  "controllerId": "CTRL-GATE-01",
  "state": "pending",
  "approved": false,
  "controllerToken": "..."
}
```

## Quy trình duyệt controller

1. Vào Odoo > Entry Control > Controllers.
2. Mở controller vừa discover.
3. Kiểm tra Controller ID, Last Seen IP, API Port.
4. Bấm `Approve`.
5. Odoo sẽ copy `Last Seen IP` và `API Port` sang endpoint đã duyệt.

## API gửi attendance sau khi đã duyệt

```http
POST http://ODOO_HOST:8069/api/entry_control/attendance
Content-Type: application/json
X-Controller-Token: <api_token_from_odoo>
```

Payload:

```json
{
  "controllerId": "CTRL-GATE-01",
  "deviceIp": "192.168.1.201:4370",
  "apiPort": 5099,
  "events": [
    {
      "eventId": "evt-001",
      "userId": "1001",
      "eventTime": "2026-05-08T08:30:00+07:00",
      "deviceIp": "192.168.1.201:4370"
    }
  ]
}
```

## Các trường hợp bị chặn

| Trường hợp | Kết quả |
|---|---|
| Thiếu controllerId | 400 |
| Controller chưa đăng ký | 403 + security event |
| Controller chưa approve | 403 + security event |
| Controller bị block | 403 + security event |
| Sai token | 401 + security event |
| Source IP khác Approved IP | 403 + chuyển controller sang Suspicious |
| API port khác Approved Port | 403 + chuyển controller sang Suspicious |

## Cấu hình security khuyến nghị

Tạo system parameter trong Odoo:

- `entry_control.discovery_secret`: shared secret dùng khi controller hello.
- `entry_control.trust_x_forwarded_for`: chỉ set `1` nếu Odoo chạy sau reverse proxy tin cậy.

Nếu không cấu hình `entry_control.discovery_secret`, hệ thống chạy được cho PoC nhưng không nên dùng production.
# Attendances