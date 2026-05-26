{
    "name": "T4TEK Entry Control",
    "summary": "ZKTeco entry-control device sync, attendance logs, and Odoo Attendances automation.",
    "description": """T4TEK Entry Control
====================

Clean controller-client architecture:
- Controller authenticates with Controller ID + Secret Key.
- Controller actively calls Odoo APIs; Odoo never calls into Controller.
- Odoo manages Controllers, Devices, Employee Sync Status, and Attendance Logs.
- Controller/device identity uses serial_number; employee identity uses employee code.
- Attendance Logs remain raw audit data; hr.attendance is created by manual action or scheduled automation.
""",
    "version": "19.0.30.28",
    "category": "Human Resources/Attendances",
    "author": "T4TEK",
    "maintainer": "T4TEK",
    "license": "LGPL-3",
    "depends": ["base", "hr", "hr_attendance", "web", "SEM"],
    "assets": {
        "web.assets_backend": [
            "t4tek_entry_control/static/src/js/copy_to_clipboard_action.js",
        ],
    },
    "data": [
        "security/groups.xml",
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/controller_views.xml",
        "views/device_views.xml",
        "views/employee_sync_views.xml",
        "views/attendance_views.xml",
        "views/menu_views.xml",
    ],
    "application": True,
    "installable": True,
    "auto_install": False,
}
