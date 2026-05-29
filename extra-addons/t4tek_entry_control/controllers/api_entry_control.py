import json
import re
from datetime import datetime

from odoo import fields, http, SUPERUSER_ID
from odoo.http import Response, request
import logging
_logger = logging.getLogger(__name__)

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
        # Authenticated machine API calls run under an explicit superuser env.
        # auth=none can leave request.env.user empty and trigger singleton
        # errors in downstream business models such as hr.attendance.
        try:
            request.update_env(user=SUPERUSER_ID)
            controller = request.env["entry.control.controller"].sudo().browse(controller.id)
        except Exception:
            pass
        controller.write({"last_heartbeat_at": fields.Datetime.now(), "status": "online", "last_error": False})
        return controller, None


    def _safe_datetime_value(self, value):
        """Normalize any Controller datetime into Odoo UTC-naive storage.

        New baseline: Odoo Datetime fields store UTC-naive values. If the
        Controller sends ``2026-05-27 10:02:38+07``, the stored value is
        ``2026-05-27 03:02:38``. Values without an offset are treated as
        already-naive compatibility values.
        """
        if not value:
            return False
        raw = str(value).strip().replace("T", " ")
        if not raw:
            return False
        try:
            parsed = fields.Datetime.to_datetime(raw) or datetime.fromisoformat(raw)
            if parsed and parsed.tzinfo:
                from datetime import timezone
                parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
            elif parsed:
                parsed = parsed.replace(tzinfo=None)
            return fields.Datetime.to_string(parsed) if parsed else False
        except Exception:
            return False

    def _extract_timezone_note_from_controller_value(self, value):
        """Extract the timezone suffix used for UTC conversion.

        Attendance push keeps the device wall-clock part separately from the
        offset. The model later combines them so ``10:02:38`` with ``+07:00``
        is stored as ``03:02:38`` UTC-naive in ``check_time``.
        """
     
        raw = str(value or "").strip()
        if not raw:
            return False
        if raw.endswith(("Z", "z")):
            return "+00:00"
        match = re.search(r"([+-]\d{2})(?::?(\d{2}))?$", raw)
        if match:
            return "%s:%s" % (match.group(1), match.group(2) or "00")
        return False

    def _strip_timezone_note_from_controller_value(self, value):
        raw = str(value or "").strip()
        if not raw:
            return raw
        if raw.endswith(("Z", "z")):
            return raw[:-1].strip()
        return re.sub(r"([+-]\d{2})(?::?\d{2})?$", "", raw).strip()

    def _canonical_controller_check_time(self, value):
        """Return the device-local wall-clock part of Controller check_time.

        Example: ``2026-05-27 10:02:38+07`` becomes
        ``2026-05-27 10:02:38`` here. The model then converts this local value
        with ``device_timezone`` to Odoo UTC-naive storage.
        """
        if not value:
            return False
        text = self._strip_timezone_note_from_controller_value(value).replace("T", " ").strip()
        match = re.search(r"(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})(?:\.(\d{1,6}))?", text)
        if match:
            frac = match.group(3)
            return f"{match.group(1)} {match.group(2)}" + (("." + frac[:6].ljust(6, "0")) if frac else "")
        # Last-resort parser: parse only after timezone suffix has been removed.
        try:
            parsed = fields.Datetime.to_datetime(text) or datetime.fromisoformat(text)
            return fields.Datetime.to_string(parsed.replace(tzinfo=None))
        except Exception:
            return False

    def _prepare_attendance_log_timezone_before_save(self, log):
        _logger.info("Gia tri text =>>>>>> %s",log)
        """Prepare attendance payload for UTC-canonical model storage.

        API input may contain ``check_time`` / ``checkTime`` / ``timestamp``.
        We keep the device-local wall-clock value in ``check_time`` and keep the
        offset in ``device_timezone``. The model is the single place that writes
        UTC-naive ``check_time`` to Odoo.
        """
        item = dict(log or {})
        time_keys = (
            "check_time"
        )
        raw_key = next((k for k in time_keys if item.get(k)), None)
        raw_value = item.get(raw_key) if raw_key else False
        tz_note = self._extract_timezone_note_from_controller_value(raw_value)
        canonical = self._canonical_controller_check_time(raw_value)
        if canonical:
            # Keep exact Controller wall-clock time; model converts it to UTC
            # using device_timezone before saving.
            item["check_time"] = canonical
        if tz_note and not (item.get("device_timezone") or item.get("deviceTimezone") or item.get("timezone") or item.get("tz")):
            item["device_timezone"] = tz_note
        item["_pre_save_timezone_debug"] = {
            "source_key": raw_key,
            "received_check_time": raw_value,
            "canonical_check_time": canonical,
            "device_timezone": item.get("device_timezone") or item.get("deviceTimezone") or item.get("timezone") or item.get("tz") or tz_note,
            "timezone_used_for_utc_storage": bool(tz_note),
        }
        return item

    def _employee_code_fields(self):
        """Return the employee-code fields available on hr.employee.

        The SEM module already provides ``hr.employee.code`` as Mã nhân viên.
        This Gatekeeper module does not create that field; it only uses
        it as the canonical identifier exchanged with the Controller and as the
        ZKTeco device user ID / EnrollNumber.
        """
        Employee = request.env["hr.employee"].sudo()
        preferred = ["code", "employee_code", "identification_id"]
        return [fname for fname in preferred if fname in Employee._fields]

    def _employee_code(self, employee):
        for fname in self._employee_code_fields():
            value = str(employee[fname] or "").strip()
            if value:
                return value
        return ""

    def _employee_device_password_fields(self):
        """Return hr.employee fields that may store the device login password/PIN.

        Current design: employee ``code`` / Mã nhân viên is the device user
        identifier. The employee ``pin`` from HR/SEM is only the optional
        device password, not the identifier.
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
        """Find hr.employee by API employee_id = Employee Code / Mã nhân viên.

        A numeric Odoo hr.employee.id fallback is kept only to make upgrades
        tolerant while all Controllers are moving to employee-code identifiers.
        """
        raw = str(employee_id or "").strip()
        Employee = request.env["hr.employee"].sudo()
        if not raw:
            return Employee.browse()
        for fname in self._employee_code_fields():
            emp = Employee.search([(fname, "=", raw)], limit=1)
            if emp:
                return emp
        try:
            emp = Employee.browse(int(raw)).exists()
            if emp:
                return emp
        except Exception:
            pass
        return Employee.browse()

    @http.route("/api/entry_control/v1/health", type="http", auth="none", methods=["GET", "POST"], csrf=False)
    def health(self, **kwargs):
        attendance_timezone = request.env["entry.control.attendance.log"].sudo()._attendance_timezone_name()
        return self._json_response({
            "ok": True,
            "service": "t4tek_entry_control",
            "status": "running",
            "attendance_timezone": attendance_timezone,
            "server_time": fields.Datetime.to_string(fields.Datetime.now()),
        })

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

    def _safe_positive_int(self, value, default=1):
        try:
            parsed = int(value)
            return parsed if parsed > 0 else default
        except Exception:
            return default

    @http.route("/api/entry_control/v1/employees", type="http", auth="none", methods=["POST"], csrf=False)
    def employees(self, **kwargs):
        data = self._read_json_body()
        controller, error = self._auth_controller(data)
        if error:
            return error

        # Current clean design: employee_id in this API is Employee Code /
        # Mã nhân viên. Controller must use this value as the device user ID /
        # ZKTeco EnrollNumber. The employee pin is only the optional device
        # password/PIN.
        #
        # Pagination contract:
        #   request:  page/page_size or offset/limit
        #   response: items + has_more + next_page/next_offset
        # page_size is capped at 100 so the Controller never receives 1000+
        # employees in a single response. `sync_cursor_to` keeps all pages in
        # one stable snapshot while paging through changed employees.
        last_sync_at = data.get("last_sync_at") or data.get("lastSyncAt")
        include_inactive = bool(data.get("include_inactive") or data.get("includeInactive"))

        requested_page_size = (
            data.get("page_size")
            or data.get("pageSize")
            or data.get("limit")
            or 100
        )
        page_size = min(max(self._safe_positive_int(requested_page_size, 100), 1), 100)
        page = self._safe_positive_int(data.get("page") or data.get("pageIndex"), 1)
        if data.get("offset") is not None:
            try:
                offset = max(int(data.get("offset") or 0), 0)
                page = (offset // page_size) + 1
            except Exception:
                offset = (page - 1) * page_size
        else:
            offset = (page - 1) * page_size

        server_sync_at = fields.Datetime.now()
        snapshot_raw = (
            data.get("sync_cursor_to")
            or data.get("syncCursorTo")
            or data.get("snapshot_sync_at")
            or data.get("snapshotSyncAt")
        )
        snapshot_sync_at = self._safe_datetime_value(snapshot_raw) if snapshot_raw else fields.Datetime.to_string(server_sync_at)

        Employee = request.env["hr.employee"].sudo()
        domain = []
        if "active" in Employee._fields and not include_inactive:
            domain.append(("active", "=", True))
        employee_code_fields = self._employee_code_fields()
        if employee_code_fields:
            primary_code_field = employee_code_fields[0]
            domain.append((primary_code_field, "!=", False))
            domain.append((primary_code_field, "!=", ""))
        if last_sync_at:
            cursor_dt = self._safe_datetime_value(last_sync_at)
            if cursor_dt:
                domain.append(("write_date", ">", cursor_dt))
        if snapshot_sync_at:
            domain.append(("write_date", "<=", snapshot_sync_at))

        total_count = Employee.search_count(domain)
        employees = Employee.search(domain, order="write_date asc, id asc", limit=page_size, offset=offset)
        items = []
        for emp in employees:
            employee_code = self._employee_code(emp)
            if not employee_code:
                continue
            device_password = self._employee_device_password(emp)
            items.append({
                # Canonical device identifier. Controller should use this as
                # the ZKTeco EnrollNumber/User ID when syncing users.
                "employee_id": employee_code,
                "employee_code": employee_code,
                # Keep the Odoo database ID only for diagnostics; do not use it
                # as the device identifier.
                "odoo_employee_id": emp.id,
                "name": emp.name or emp.display_name,
                # Device password/PIN. This is NOT the device user identifier.
                "pin": device_password,
                "active": bool(emp.active) if "active" in emp._fields else True,
                "write_date": fields.Datetime.to_string(emp.write_date),
            })

        # Make Employee Sync Status visible as soon as a Controller successfully
        # pulls each page, but do not overwrite an already-successful Controller
        # report on every incremental poll. Only mark pending when the row is new
        # or the employee changed after the last successful report.
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
                "error_message": "Sent to Controller by /api/entry_control/v1/employees page %s; waiting for /employees/sync-status." % page,
            })
            if rec:
                rec.write(vals)
            else:
                Sync.create(vals)
            pending_count += 1

        has_more = (offset + len(employees)) < total_count
        next_offset = offset + len(items) if has_more else False
        next_page = page + 1 if has_more else False
        controller.write({"last_sync_at": server_sync_at})
        return self._json_response({
            "ok": True,
            "count": len(items),
            "total_count": total_count,
            "total": total_count,
            "page": page,
            "page_size": page_size,
            "limit": page_size,
            "offset": offset,
            "has_more": has_more,
            "next_page": next_page,
            "next_offset": next_offset,
            "employees": items,
            "items": items,
            "server_sync_at": fields.Datetime.to_string(server_sync_at),
            "sync_cursor_to": snapshot_sync_at,
            "snapshot_sync_at": snapshot_sync_at,
            "last_sync_at_received": last_sync_at or False,
            "employee_code_fields": self._employee_code_fields(),
            "pin_fields": self._employee_device_password_fields(),
            "employee_sync_status_pending": pending_count,
            "employee_sync_status_preserved": preserved_count,
            "note": "employee_id is Employee Code / Mã nhân viên; odoo_employee_id is diagnostic only; pin is the optional device password/PIN; employees are paged and page_size is capped at 100",
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
                api_employee_id = str(item.get("employee_id") or item.get("employeeId") or item.get("employee_code") or item.get("employeeCode") or "").strip()
                emp = self._find_employee_by_api_employee_id(api_employee_id)
                if not emp:
                    raise ValueError("employee_id / employee_code not found on Employee Code / Mã nhân viên: %s" % api_employee_id)
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
        serial_numbers = []
        failed = []
        for idx, dev in enumerate(devices if isinstance(devices, list) else []):
            rec = Device.upsert_from_payload(controller, dev)
            if rec:
                ids.append(rec.id)
                serial_numbers.append(rec.serial_number)
            else:
                failed.append({"index": idx, "error": "serial_number is required; device IP is not a valid identifier"})
        controller.write({"last_sync_at": fields.Datetime.now()})
        return self._json_response({
            "ok": not bool(failed),
            "count": len(ids),
            "device_ids": ids,
            "serial_numbers": serial_numbers,
            "failed": failed,
            "note": "Device identity is Serial Number. IP address is informational only and may overlap between sites.",
        }, 200 if not failed else 207)

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
                _logger.info("--- [API PUSH] Log index %s từ thiết bị gửi lên: %s", idx, str(log))
                rec, duplicate = Log.ingest_direct_log(controller, log)
                _logger.info("--- [ingest_direct_log] Log index %s đã xử lý: %s", idx, str(log))
                results.append({
                    "index": idx,
                    "attendance_log_id": rec.id,
                    "success": rec.sync_status != "failed",
                    "status": "success" if rec.sync_status != "failed" else "failed",
                    "message": rec.error_message or "",
                    "direction": rec.direction,
                    "device_timezone": rec.device_timezone,
                    "duplicate": duplicate,
                })
                if rec.sync_status == "failed":
                    failed.append({"index": idx, "error": rec.error_message or "Failed"})
                    
            except Exception as e:
                failed.append({"index": idx, "error": str(e)})
                
        controller.write({"last_sync_at": fields.Datetime.now()})
        
        return self._json_response({
            "ok": not bool(failed), 
            "received": len(logs), 
            "results": results, 
            "items": results, 
            "failed": failed
        }, 200 if not failed else 207)