from datetime import timezone
from functools import lru_cache
from zoneinfo import ZoneInfo, available_timezones

from odoo import api, fields, models, _
from odoo.exceptions import UserError

@lru_cache(maxsize=1)
def _module_tz_get():
    """Return IANA timezones for the Settings dropdown.

    Keep this local instead of depending on Odoo user timezone defaults, so the
    Gatekeeper module timezone remains a module-level business setting.
    """
    zones = sorted(available_timezones())
    if "Asia/Ho_Chi_Minh" not in zones:
        zones.insert(0, "Asia/Ho_Chi_Minh")
    return [(tz, tz) for tz in zones]


def _tz_get(self):
    return _module_tz_get()


class EntryControlSettings(models.TransientModel):
    _name = "entry.control.settings"
    _description = "Gatekeeper Settings"

    attendance_timezone = fields.Selection(
        _tz_get,
        string="Default Timezone",
        required=True,
        default="Asia/Ho_Chi_Minh",
        help="Fallback timezone used for new Controllers and legacy records without Controller. Normal attendance processing uses each Controller Timezone.",
    )
    daily_cron_local_run_time = fields.Char(
        string="Daily Local Processing Time",
        default="00:00",
        help="Local time in each Controller Timezone when the periodic UTC cron is allowed to process the previous business day. Format: HH:MM, for example 00:00 or 00:15.",
    )
    controller_heartbeat_timeout_seconds = fields.Integer(
        string="Controller Heartbeat Timeout (seconds)",
        default=300,
        help="If Odoo does not receive any Controller API call within this timeout, the server-side watchdog marks the Controller offline and its Devices unknown.",
    )

    last_cron_at_utc = fields.Char(string="Last Cron Run UTC", readonly=True)
    last_cron_at_local = fields.Char(string="Last Cron Run Local", readonly=True)
    last_cron_date = fields.Char(string="Last Business Date", readonly=True)
    last_cron_timezone = fields.Char(string="Last Cron Timezone", readonly=True)
    last_cron_db_start = fields.Char(string="Last DB Start UTC", readonly=True)
    last_cron_db_end = fields.Char(string="Last DB End UTC", readonly=True)
    last_cron_log_count = fields.Char(string="Last Log Count", readonly=True)
    last_cron_employee_count = fields.Char(string="Last Employee Count", readonly=True)
    last_cron_created_count = fields.Char(string="Last Created Attendances", readonly=True)
    last_cron_updated_count = fields.Char(string="Last Updated Attendances", readonly=True)
    last_cron_failed_count = fields.Char(string="Last Failed Count", readonly=True)

    @api.model
    def _log_model(self):
        return self.env["entry.control.attendance.log"].sudo()

    @api.model
    def _default_attendance_timezone(self):
        return self._log_model()._attendance_timezone_name()

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        Log = self._log_model()
        ICP = self.env["ir.config_parameter"].sudo()
        if "attendance_timezone" in fields_list:
            res["attendance_timezone"] = self._default_attendance_timezone() or "Asia/Ho_Chi_Minh"
        if "daily_cron_local_run_time" in fields_list:
            res["daily_cron_local_run_time"] = ICP.get_param(Log._CONFIG_CRON_LOCAL_RUN_TIME, Log._DEFAULT_CRON_LOCAL_RUN_TIME)
        if "controller_heartbeat_timeout_seconds" in fields_list:
            try:
                res["controller_heartbeat_timeout_seconds"] = int(ICP.get_param("entry_control.controller_heartbeat_timeout_seconds", "300") or 300)
            except Exception:
                res["controller_heartbeat_timeout_seconds"] = 300

        metric_map = {
            "last_cron_at_utc": Log._CONFIG_CRON_LAST_AT_UTC,
            "last_cron_at_local": Log._CONFIG_CRON_LAST_AT_LOCAL,
            "last_cron_date": Log._CONFIG_CRON_LAST_DATE,
            "last_cron_timezone": Log._CONFIG_CRON_LAST_TIMEZONE,
            "last_cron_db_start": Log._CONFIG_CRON_LAST_DB_START,
            "last_cron_db_end": Log._CONFIG_CRON_LAST_DB_END,
            "last_cron_log_count": Log._CONFIG_CRON_LAST_LOG_COUNT,
            "last_cron_employee_count": Log._CONFIG_CRON_LAST_EMPLOYEE_COUNT,
            "last_cron_created_count": Log._CONFIG_CRON_LAST_CREATED_COUNT,
            "last_cron_updated_count": Log._CONFIG_CRON_LAST_UPDATED_COUNT,
            "last_cron_failed_count": Log._CONFIG_CRON_LAST_FAILED_COUNT,
        }
        for field_name, param_name in metric_map.items():
            if field_name in fields_list:
                res[field_name] = ICP.get_param(param_name, "")

        # Backward-compatible display for databases upgraded from older builds
        # that only stored `entry_control.last_daily_attendance_cron_at`.
        legacy_utc = ICP.get_param(Log._CONFIG_CRON_LAST_AT, "")
        if "last_cron_at_utc" in fields_list and not res.get("last_cron_at_utc"):
            res["last_cron_at_utc"] = legacy_utc
        if "last_cron_at_local" in fields_list and not res.get("last_cron_at_local") and legacy_utc:
            try:
                utc_dt = fields.Datetime.from_string(legacy_utc).replace(tzinfo=timezone.utc)
                local_dt = utc_dt.astimezone(Log._attendance_zoneinfo())
                res["last_cron_at_local"] = Log._format_module_local_datetime(local_dt)
            except Exception:
                res["last_cron_at_local"] = ""
        return res

    def _validate_timezone(self, tz_name):
        tz_name = str(tz_name or "").strip()
        if not tz_name:
            raise UserError(_("Default Timezone is required."))
        try:
            ZoneInfo(tz_name)
        except Exception:
            raise UserError(_("Invalid timezone '%s'. Please use an IANA timezone name, for example Asia/Ho_Chi_Minh.") % tz_name)
        return tz_name

    def _validate_local_run_time(self, value):
        text = str(value or "00:00").strip()
        parts = text.split(":")
        if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
            raise UserError(_("Daily Local Processing Time must use HH:MM format, for example 00:00 or 00:15."))
        hour = int(parts[0])
        minute = int(parts[1])
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise UserError(_("Daily Local Processing Time must be between 00:00 and 23:59."))
        return "%02d:%02d" % (hour, minute)

    def _validate_heartbeat_timeout_seconds(self, value):
        try:
            seconds = int(value or 300)
        except Exception:
            raise UserError(_("Controller Heartbeat Timeout must be a number of seconds."))
        if seconds < 60:
            raise UserError(_("Controller Heartbeat Timeout must be at least 60 seconds."))
        return seconds

    def _check_gatekeeper_admin(self):
        if not (self.env.user.has_group("t4tek_entry_control.group_entry_control_admin") or self.env.user.has_group("base.group_system")):
            raise UserError(_("Only Gatekeeper Administrators can change Gatekeeper Settings."))

    def action_save(self):
        self.ensure_one()
        self._check_gatekeeper_admin()
        tz_name = self._validate_timezone(self.attendance_timezone)
        run_time = self._validate_local_run_time(self.daily_cron_local_run_time)
        heartbeat_timeout = self._validate_heartbeat_timeout_seconds(self.controller_heartbeat_timeout_seconds)
        Log = self._log_model()
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param(Log._CONFIG_ATTENDANCE_TIMEZONE, tz_name)
        ICP.set_param(Log._CONFIG_CRON_LOCAL_RUN_TIME, run_time)
        ICP.set_param("entry_control.controller_heartbeat_timeout_seconds", str(heartbeat_timeout))
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Gatekeeper Settings"),
                "message": _("Default timezone saved: %s. Daily local processing time: %s. Heartbeat timeout: %s seconds.") % (tz_name, run_time, heartbeat_timeout),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def action_reset_default(self):
        self.ensure_one()
        self._check_gatekeeper_admin()
        Log = self._log_model()
        tz_name = Log._DEFAULT_ATTENDANCE_TIMEZONE
        run_time = Log._DEFAULT_CRON_LOCAL_RUN_TIME
        heartbeat_timeout = 300
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param(Log._CONFIG_ATTENDANCE_TIMEZONE, tz_name)
        ICP.set_param(Log._CONFIG_CRON_LOCAL_RUN_TIME, run_time)
        ICP.set_param("entry_control.controller_heartbeat_timeout_seconds", str(heartbeat_timeout))
        self.attendance_timezone = tz_name
        self.daily_cron_local_run_time = run_time
        self.controller_heartbeat_timeout_seconds = heartbeat_timeout
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Gatekeeper Settings"),
                "message": _("Default timezone reset to default: %s. Daily local processing time reset to %s") % (tz_name, run_time),
                "type": "success",
                "sticky": False,
            },
        }
