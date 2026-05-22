# -*- coding: utf-8 -*-
{
    'name': 'T4 Admin Center',
    'version': '1.0',
    'category': 'Administration',
    'sequence': 5,
    'summary': 'Trung tâm quản trị hệ thống',
    'description': """
T4 Admin Center
===============
Module quản trị tập trung cho phép Admin được phân quyền thực hiện:

* Quản lý Máy chủ Mail đến (Incoming Mail Server - IMAP/POP3)
* Quản lý Máy chủ Mail đi (Outgoing Mail Server - SMTP)
* Quản lý Mẫu Email (Mail Template) - đặc biệt template Reset mật khẩu
* Cấu hình nhận/gửi mail cho từng đối tác (res.partner)
* Chỉnh sửa thông tin công ty
    """,
    'author': 'T4TEK-DEV',
    'website': 'https://t4tek.co',
    'depends': [
        'base',
        'mail',
        'base_setup',
        'contacts',
    ],
    'data': [
        # Security (phải load trước)
        'security/t4_admin_center_security.xml',
        'security/ir.model.access.csv',
        # Views + Actions (phải load trước menu)
        'views/fetchmail_views.xml',
        'views/ir_mail_server_views.xml',
        'views/mail_template_views.xml',
        'views/res_partner_views.xml',
        'views/mail_message_views.xml',
        # Menus (phải load SAU khi tất cả actions đã được tạo)
        'views/t4_admin_center_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            't4_admin_center/static/src/js/dynamic_placeholder_patch.js',
        ],
    },
    'application': True,
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
