{
    "name": "T4TEK Attendance Gateway",
    "summary": "Controller-based ZKTeco attendance gateway for Odoo Attendances.",
    "description": """T4TEK Attendance Gateway
========================

Clean controller-client architecture:
- Controller authenticates with Controller ID + Secret Key.
- Controller actively calls Odoo APIs; Odoo never calls into Controller.
- Odoo manages Controllers, Devices, Employee Sync Status, and Attendance Logs.
- Odoo does not track user-to-device sync status; that stays local to Controller.
- Attendance Logs are converted to hr.attendance using server-side direction inference.
""",
    "version": "19.0.30.10",
    "category": "Human Resources/Attendances",
    "author": "T4TEK",
    "maintainer": "T4TEK",
    "license": "LGPL-3",
    "depends": ["base", "hr", "hr_attendance", "web"],
    "assets": {
        "web.assets_backend": [
            "t4tek_entry_control/static/src/js/copy_to_clipboard_action.js",
        ],
    },
    "data": [
        "security/groups.xml",
        "security/ir.model.access.csv",
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
