import json
from datetime import datetime, timezone

from odoo import fields, http
from odoo.http import Response, request


class EntryControlAPI(http.Controller):
    def _json_response(self, payload, status=200):
        return Response(json.dumps(payload, ensure_ascii=False, default=str), content_type="application/json", status=status)

    def _read_json_body(self):
        raw = request.httprequest.data
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        except Exception:
            return {}

    def _controller_uid_from_data(self, data):
        return (request.httprequest.headers.get("X-Controller-ID")
                or request.httprequest.headers.get("X-Controller-Code")
                or data.get("controller_uid")
                or data.get("controller_id")
                or data.get("controller_code")
                or data.get("controllerCode")
                or "").strip().upper()

    def _bearer_token(self, data=None):
        auth = request.httprequest.headers.get("Authorization") or ""
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
        data = data or {}
        return (request.httprequest.headers.get("X-Controller-Token")
                or data.get("access_token")
                or data.get("controller_token")
                or "").strip()

    def _auth_controller(self, data=None):
        data = data or self._read_json_body()
        uid = self._controller_uid_from_data(data)
        if not uid:
            return None, self._json_response({"ok": False, "error": "controller_uid is required"}, 400)
        controller = request.env["entry.control.controller"].sudo().search([("controller_uid", "=", uid)], limit=1)
        if not controller:
            return None, self._json_response({"ok": False, "error": "Unknown controller_uid"}, 404)
        if not controller.active or controller.status == "blocked":
            controller.write({"last_error": "Blocked/inactive controller attempted API call."})
            return None, self._json_response({"ok": False, "error": "Controller is blocked or inactive"}, 403)
        token = self._bearer_token(data)
        if not controller.check_access_token(token):
            return None, self._json_response({"ok": False, "error": "Invalid or expired access token"}, 401)
        controller.write({"last_heartbeat_at": fields.Datetime.now(), "status": "online", "last_error": False})
        return controller, None


    def _safe_datetime_value(self, value):
        """Accept Odoo datetime strings and Controller ISO datetime strings.

        Controller .NET may send values like 2026-05-25T10:04:03.1234567+07:00.
        Odoo Datetime fields store naive UTC strings, so normalize here before ORM write.
        """
        if not value:
            return False
        raw = str(value).strip()
        if not raw:
            return False
        try:
            parsed = fields.Datetime.to_datetime(raw)
            if parsed:
                return fields.Datetime.to_string(parsed)
        except Exception:
            pass
        try:
            iso = raw.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(iso)
            if parsed.tzinfo:
                parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
            return fields.Datetime.to_string(parsed)
        except Exception:
            return False

    def _employee_device_password_fields(self):
        """Return hr.employee fields that may store the device login password/PIN.

        Latest design: `employee_id` in API payloads is the numeric Odoo
        `hr.employee.id`. The employee `pin` is only the password/PIN used
        when creating the user on the ZKTeco device, not the user identifier.
        """
        Employee = request.env["hr.employee"].sudo()
        preferred = ["pin", "entry_control_pin"]
        return [fname for fname in preferred if fname in Employee._fields]

    def _employee_device_password(self, employee):
        for fname in self._employee_device_password_fields():
            value = str(employee[fname] or "").strip()
            if value:
                return value
        return ""

    # Backward-compatible helper names used by older code paths.
    def _employee_pin_fields(self):
        return self._employee_device_password_fields()

    def _employee_pin(self, employee):
        return self._employee_device_password(employee)

    def _find_employee_by_api_employee_id(self, employee_id):
        """Find hr.employee by the canonical API employee_id = hr.employee.id."""
        raw = str(employee_id or "").strip()
        Employee = request.env["hr.employee"].sudo()
        if not raw:
            return Employee.browse()
        try:
            emp = Employee.browse(int(raw)).exists()
            if emp:
                return emp
        except Exception:
            pass
        return Employee.browse()

    @http.route("/api/entry_control/v1/health", type="http", auth="none", methods=["GET", "POST"], csrf=False)
    def health(self, **kwargs):
        return self._json_response({"ok": True, "service": "t4tek_entry_control", "status": "running", "server_time": fields.Datetime.to_string(fields.Datetime.now())})

    @http.route("/api/entry_control/v1/auth/token", type="http", auth="none", methods=["POST"], csrf=False)
    def auth_token(self, **kwargs):
        data = self._read_json_body()
        uid = self._controller_uid_from_data(data)
        secret = str(data.get("secret_key") or data.get("secretKey") or data.get("odoo_password") or "").strip()
        if not uid or not secret:
            return self._json_response({"ok": False, "error": "controller_uid and secret_key are required"}, 400)
        controller = request.env["entry.control.controller"].sudo().search([("controller_uid", "=", uid)], limit=1)
        if not controller:
            return self._json_response({"ok": False, "error": "Unknown controller_uid"}, 401)
        if not controller.active or controller.status == "blocked":
            return self._json_response({"ok": False, "error": "Controller is blocked or inactive"}, 403)
        if secret != (controller.secret_key or ""):
            controller.write({"last_error": "Invalid secret key authentication attempt."})
            return self._json_response({"ok": False, "error": "Invalid secret_key"}, 401)
        access_token, refresh_token = controller.issue_tokens()
        return self._json_response({
            "ok": True,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": fields.Datetime.to_string(controller.token_expires_at),
            "refresh_expires_at": fields.Datetime.to_string(controller.refresh_token_expires_at),
            "token_hint": controller.token_hint,
            "controller_uid": controller.controller_uid,
            "registration_status": controller.status,
            "approved": True,
            "message": "Authenticated",
        })

    @http.route("/api/entry_control/v1/auth/refresh", type="http", auth="none", methods=["POST"], csrf=False)
    def auth_refresh(self, **kwargs):
        data = self._read_json_body()
        refresh_token = str(data.get("refresh_token") or data.get("refreshToken") or "").strip()
        uid = self._controller_uid_from_data(data)
        Controller = request.env["entry.control.controller"].sudo()
        domain = [("controller_uid", "=", uid)] if uid else []
        for controller in Controller.search(domain):
            if not controller.check_refresh_token(refresh_token):
                continue
            if not controller.active or controller.status == "blocked":
                controller.write({"last_error": "Blocked/inactive controller attempted token refresh."})
                return self._json_response({"ok": False, "error": "Controller is blocked or inactive"}, 403)
            access_token, new_refresh_token = controller.issue_tokens()
            return self._json_response({
                "ok": True,
                "access_token": access_token,
                "refresh_token": new_refresh_token,
                "expires_at": fields.Datetime.to_string(controller.token_expires_at),
                "refresh_expires_at": fields.Datetime.to_string(controller.refresh_token_expires_at),
                "token_hint": controller.token_hint,
            })
        return self._json_response({"ok": False, "error": "Invalid refresh_token"}, 401)

    @http.route("/api/entry_control/v1/hello", type="http", auth="none", methods=["POST"], csrf=False)
    def hello(self, **kwargs):
        data = self._read_json_body()
        controller, error = self._auth_controller(data)
        if error:
            return error
        controller.write({"last_heartbeat_at": fields.Datetime.now(), "last_sync_at": fields.Datetime.now(), "status": "online"})
        return self._json_response({"ok": True, "controller_uid": controller.controller_uid, "status": controller.status, "approved": True, "message": "Hello OK"})

    @http.route("/api/entry_control/v1/employees", type="http", auth="none", methods=["POST"], csrf=False)
    def employees(self, **kwargs):
        data = self._read_json_body()
        controller, error = self._auth_controller(data)
        if error:
            return error

        # Latest clean design: employee_id in this API is the canonical
        # Odoo hr.employee.id. The employee pin is the device password/PIN.
        last_sync_at = data.get("last_sync_at") or data.get("lastSyncAt")
        include_inactive = bool(data.get("include_inactive") or data.get("includeInactive"))
        server_sync_at = fields.Datetime.now()

        Employee = request.env["hr.employee"].sudo()
        domain = []
        if "active" in Employee._fields and not include_inactive:
            domain.append(("active", "=", True))
        if last_sync_at:
            cursor_dt = self._safe_datetime_value(last_sync_at)
            if cursor_dt:
                domain.append(("write_date", ">", cursor_dt))
            else:
                # Invalid cursor should not break the controller pull; treat it as full pull.
                domain = [(d[0], d[1], d[2]) for d in domain if d[0] != "write_date"]

        employees = Employee.search(domain, order="write_date asc, id asc")
        items = []
        for emp in employees:
            device_password = self._employee_device_password(emp)
            items.append({
                # Canonical Odoo employee identifier. Controller should use this
                # as the device user ID / ZKTeco EnrollNumber when syncing users.
                "employee_id": emp.id,
                "name": emp.name or emp.display_name,
                # Device password/PIN. This is NOT the device user identifier.
                "pin": device_password,
                "active": bool(emp.active) if "active" in emp._fields else True,
                "write_date": fields.Datetime.to_string(emp.write_date),
            })

        # Make Employee Sync Status visible as soon as a Controller successfully
        # pulls the employee list, but do not overwrite an already-successful
        # Controller report on every incremental poll. Only mark pending when the
        # row is new or the employee changed after the last successful report.
        Sync = request.env["entry.control.employee.sync"].sudo()
        pending_count = 0
        preserved_count = 0
        for emp, item in zip(employees, items):
            common_vals = {
                "controller_id": controller.id,
                "employee_id": emp.id,
                "employee_name": emp.name or emp.display_name,
            }
            rec = Sync.search([("controller_id", "=", controller.id), ("employee_id", "=", emp.id)], limit=1)
            keep_reported_status = False
            if rec and rec.sync_status in ("success", "skipped") and rec.last_synced_at and emp.write_date:
                try:
                    keep_reported_status = rec.last_synced_at >= emp.write_date
                except Exception:
                    keep_reported_status = False
            if rec and keep_reported_status:
                rec.write(common_vals)
                preserved_count += 1
                continue
            vals = dict(common_vals)
            vals.update({
                "last_synced_at": server_sync_at,
                "sync_status": "pending",
                "error_message": "Sent to Controller by /api/entry_control/v1/employees; waiting for /employees/sync-status.",
            })
            if rec:
                rec.write(vals)
            else:
                Sync.create(vals)
            pending_count += 1

        controller.write({"last_sync_at": server_sync_at})
        return self._json_response({
            "ok": True,
            "count": len(items),
            "employees": items,
            "items": items,
            "server_sync_at": fields.Datetime.to_string(server_sync_at),
            "last_sync_at_received": last_sync_at or False,
            "pin_fields": self._employee_device_password_fields(),
            "employee_sync_status_pending": pending_count,
            "employee_sync_status_preserved": preserved_count,
            "note": "employee_id is hr.employee.id; pin is the device password/PIN",
        })

    @http.route("/api/entry_control/v1/employees/sync-status", type="http", auth="none", methods=["POST"], csrf=False)
    def employees_sync_status(self, **kwargs):
        data = self._read_json_body()
        controller, error = self._auth_controller(data)
        if error:
            return error
        items = data.get("items") or []
        Sync = request.env["entry.control.employee.sync"].sudo()
        Employee = request.env["hr.employee"].sudo()
        ok_count = 0
        failed = []
        for idx, item in enumerate(items if isinstance(items, list) else []):
            try:
                api_employee_id = str(item.get("employee_id") or item.get("employeeId") or "").strip()
                emp = self._find_employee_by_api_employee_id(api_employee_id)
                if not emp:
                    raise ValueError("employee_id not found on hr.employee.id: %s" % api_employee_id)
                vals = {
                    "controller_id": controller.id,
                    "employee_id": emp.id,
                    "employee_name": emp.name or emp.display_name,
                    "last_synced_at": self._safe_datetime_value(item.get("last_synced_at") or item.get("lastSyncedAt")) or fields.Datetime.now(),
                    "sync_status": item.get("sync_status") or item.get("status") or "success",
                    "error_message": item.get("error_message") or item.get("error") or "",
                }
                rec = Sync.search([("controller_id", "=", controller.id), ("employee_id", "=", emp.id)], limit=1)
                if rec:
                    rec.write(vals)
                else:
                    Sync.create(vals)
                ok_count += 1
            except Exception as e:
                failed.append({"index": idx, "error": str(e)})
        controller.write({"last_sync_at": fields.Datetime.now()})
        return self._json_response({"ok": not bool(failed), "count": ok_count, "failed": failed}, 200 if not failed else 207)

    @http.route("/api/entry_control/v1/devices/report", type="http", auth="none", methods=["POST"], csrf=False)
    def devices_report(self, **kwargs):
        data = self._read_json_body()
        controller, error = self._auth_controller(data)
        if error:
            return error
        devices = data.get("devices") or []
        if isinstance(devices, dict):
            devices = [devices]
        Device = request.env["entry.control.device"].sudo()
        ids = []
        for dev in devices if isinstance(devices, list) else []:
            rec = Device.upsert_from_payload(controller, dev)
            if rec:
                ids.append(rec.id)
        controller.write({"last_sync_at": fields.Datetime.now()})
        return self._json_response({"ok": True, "count": len(ids), "device_ids": ids})

    @http.route("/api/entry_control/v1/attendance/logs/push", type="http", auth="none", methods=["POST"], csrf=False)
    def attendance_logs_push(self, **kwargs):
        data = self._read_json_body()
        controller, error = self._auth_controller(data)
        if error:
            return error
        logs = data.get("logs") or []
        if isinstance(logs, dict):
            logs = [logs]
        Log = request.env["entry.control.attendance.log"].sudo()
        results = []
        failed = []
        for idx, log in enumerate(logs if isinstance(logs, list) else []):
            try:
                rec, duplicate = Log.ingest_direct_log(controller, log)
                results.append({
                    "index": idx,
                    "local_id": log.get("local_id") or log.get("id"),
                    "attendance_log_id": rec.id,
                    "success": rec.sync_status != "failed",
                    "status": "success" if rec.sync_status != "failed" else "failed",
                    "message": rec.error_message or "",
                    "direction": rec.direction,
                    "duplicate": duplicate,
                })
                if rec.sync_status == "failed":
                    failed.append({"index": idx, "error": rec.error_message or "Failed"})
            except Exception as e:
                failed.append({"index": idx, "error": str(e)})
        controller.write({"last_sync_at": fields.Datetime.now()})
        return self._json_response({"ok": not bool(failed), "received": len(logs), "results": results, "items": results, "failed": failed}, 200 if not failed else 207)
