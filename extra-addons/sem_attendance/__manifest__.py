# -*- coding: utf-8 -*-
{
    'name': 'System Employee Management - Attendance',
    'version': '19.0.1.0.0',
    'summary': 'Chấm công cho hệ thống quản lý nhân sự SEM',
    'sequence': -20000,
    'description': """
    "sequence": -100,
Mô đun quản lý chấm công, tách riêng từ SEM gốc.
Bao gồm tính năng xem Grid Calendar và popup chấm công.
    """,
    'category': 'SEMs',
    'depends': ['base', 'hr', 'hr_attendance', "hr_holidays", 'SEM', 'web', 'mail'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/attendance_cron.xml',
        'views/hr_attendance_views.xml',
        'views/hr_employee_inherit.xml',
        'views/hr_time_off_views.xml',
        'views/hr_leave_inherit.xml',
        'views/attendance_dashboard_views.xml',
        'views/hr_attendance_calendar_views.xml',
        'views/hr_config_settings_views.xml',
        'views/attendance_report.xml',
        'wizard/import_attendance_wizard_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sem_attendance/static/src/css/attendance_dashboard.scss',
            'sem_attendance/static/src/js/dashboard/dashboard_service.js',
            'sem_attendance/static/src/js/dashboard/attendance_dashboard.js',
            'sem_attendance/static/src/js/dashboard/attendance_dashboard.xml',
            'sem_attendance/static/src/views/calendar/**/*.scss',
            'sem_attendance/static/src/views/calendar/**/*.js',
            'sem_attendance/static/src/views/calendar/**/*.xml',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
