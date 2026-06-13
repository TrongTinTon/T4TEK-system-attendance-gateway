from datetime import timedelta

from odoo import api, fields, models, _


class EntryControlAttendanceCronRun(models.Model):
    _name = "entry.control.attendance.cron.run"
    _description = "Gatekeeper Attendance Processing Ledger"
    _order = "controller_id, id desc"
    _rec_name = "display_name"

    display_name = fields.Char(compute="_compute_display_name", store=False)
    controller_id = fields.Many2one(
        "entry.control.controller",
        string="Controller",
        required=True,
        index=True,
        ondelete="cascade",
    )
    business_date = fields.Date(string="Last Processed Business Date", required=True, index=True)
    timezone = fields.Char(string="Controller Timezone", required=True)
    local_run_time = fields.Char(string="Local Run Time", default="00:00")
    due_at_utc = fields.Datetime(string="Due At UTC", index=True)
    local_started_at = fields.Char(string="Started At Local", readonly=True)
    status = fields.Selection([
        ("pending", "Pending"),
        ("running", "Running"),
        ("done", "Done"),
        ("failed", "Failed"),
    ], default="pending", required=True, index=True)
    started_at = fields.Datetime(string="Started At UTC", readonly=True)
    finished_at = fields.Datetime(string="Finished At UTC", readonly=True)
    employee_count = fields.Integer(readonly=True)
    log_count = fields.Integer(readonly=True)
    created_count = fields.Integer(readonly=True)
    updated_count = fields.Integer(readonly=True)
    skipped_count = fields.Integer(readonly=True)
    failed_count = fields.Integer(readonly=True)
    db_start = fields.Datetime(string="DB Start UTC", readonly=True)
    db_end = fields.Datetime(string="DB End UTC", readonly=True)
    error_message = fields.Text(readonly=True)

    _sql_constraints = [
        # Keep the legacy DB constraint for backward compatibility with existing
        # databases. The runtime logic below now keeps only one ledger row per
        # Controller and updates that row as a snapshot.
        (
            "controller_business_date_unique",
            "unique(controller_id, business_date)",
            "This Controller business date has already been scheduled or processed.",
        ),
    ]

    def init(self):
        """Collapse legacy per-day ledger rows into one row per Controller.

        Older versions stored one ledger row for each ``controller_id +
        business_date``. This version keeps one snapshot row per Controller. On
        module upgrade, keep the newest business date for each Controller and
        remove older rows before creating the uniqueness guard.
        """
        self.env.cr.execute("""
            WITH ranked AS (
                SELECT
                    id,
                    row_number() OVER (
                        PARTITION BY controller_id
                        ORDER BY business_date DESC NULLS LAST, write_date DESC NULLS LAST, id DESC
                    ) AS rn
                FROM entry_control_attendance_cron_run
                WHERE controller_id IS NOT NULL
            )
            DELETE FROM entry_control_attendance_cron_run r
            USING ranked
            WHERE r.id = ranked.id
              AND ranked.rn > 1
        """)
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS entry_control_attendance_cron_run_controller_unique_idx
            ON entry_control_attendance_cron_run (controller_id)
            WHERE controller_id IS NOT NULL
        """)

    @api.depends("controller_id", "business_date", "status")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s / %s / %s" % (
                rec.controller_id.display_name or "Controller",
                rec.business_date or "",
                rec.status or "",
            )

    @api.model
    def _get_or_create_controller_day_run(self, controller, business_date, timezone_name, local_run_time, due_at_utc):
        """Return the single processing ledger row for one Controller.

        New rule: the ledger is a Controller snapshot, not a per-day history
        table. Therefore each Controller owns exactly one row. The row's
        ``business_date`` represents the current/last processed business date.
        """
        controller = controller.sudo()
        business_date = fields.Date.to_date(business_date)
        runs = self.search(
            [("controller_id", "=", controller.id)],
            order="business_date desc, id desc",
        )
        run = runs[:1]
        if len(runs) > 1:
            # Backward-compatible cleanup for legacy databases that still have
            # one row per controller/day.
            (runs - run).unlink()

        vals = {
            "timezone": timezone_name or controller.attendance_timezone or "Asia/Ho_Chi_Minh",
            "local_run_time": local_run_time or "00:00",
            "due_at_utc": due_at_utc,
        }
        reset_vals = {
            "status": "pending",
            "started_at": False,
            "finished_at": False,
            "local_started_at": False,
            "employee_count": 0,
            "log_count": 0,
            "created_count": 0,
            "updated_count": 0,
            "skipped_count": 0,
            "failed_count": 0,
            "db_start": False,
            "db_end": False,
            "error_message": False,
        }
        if run:
            current_business_date = fields.Date.to_date(run.business_date) if run.business_date else False
            if current_business_date != business_date:
                if run.status == "running" and not run._is_stale_running():
                    # Do not overwrite an active run. The next cron tick will
                    # retry/update after the run finishes or becomes stale.
                    run.write(vals)
                    return run
                vals.update(reset_vals)
                vals["business_date"] = business_date
                run.write(vals)
            elif run.status in ("pending", "failed", "running"):
                run.write(vals)
            return run

        vals.update(reset_vals)
        vals.update({
            "controller_id": controller.id,
            "business_date": business_date,
        })
        return self.create(vals)

    def _is_stale_running(self):
        self.ensure_one()
        if self.status != "running" or not self.started_at:
            return False
        started_at = fields.Datetime.to_datetime(self.started_at)
        return started_at < (fields.Datetime.now() - timedelta(hours=2))

    def _mark_running(self, now_utc=None, local_now=None):
        now_utc = now_utc or fields.Datetime.now()
        for rec in self:
            rec.write({
                "status": "running",
                "started_at": now_utc,
                "finished_at": False,
                "local_started_at": str(local_now or ""),
                "error_message": False,
            })

    def _mark_done(self, metrics):
        metrics = metrics or {}
        for rec in self:
            rec.write({
                "status": "done",
                "finished_at": fields.Datetime.now(),
                "employee_count": int(metrics.get("employee_count") or 0),
                "log_count": int(metrics.get("log_count") or 0),
                "created_count": int(metrics.get("created_count") or 0),
                "updated_count": int(metrics.get("updated_count") or 0),
                "skipped_count": int(metrics.get("skipped_count") or 0),
                "failed_count": int(metrics.get("failed_count") or 0),
                "db_start": metrics.get("db_start") or False,
                "db_end": metrics.get("db_end") or False,
                "error_message": False,
            })

    def _mark_failed(self, error_message):
        for rec in self:
            rec.write({
                "status": "failed",
                "finished_at": fields.Datetime.now(),
                "failed_count": (rec.failed_count or 0) + 1,
                "error_message": error_message or _("Unknown error"),
            })
