{
    'name': 'Core App',
    'version': '1.0',
    'summary': 'A custom user and permission management module.',
    'author': 'Dat & Khoa',
    'depends': ['base','mail', 'auth_signup'],
    'sequence': -1,
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/core_app_actions.xml',
        'views/core_app_res_groups_views.xml',
        'views/core_app_role_views.xml',
        'views/core_app_simplified_views.xml',
        'views/core_app_ir_module_category_views.xml',
        'views/core_app_menu_views.xml',
        'views/core_app_menus.xml',
        'views/core_app_export_import_views.xml',

    ],
    'application': True,
    'installable': True,
    # 'post_load': 'post_hide_default_menus',
    # 'pre_init_hook': 'pre_assign_hidden_to_admin',
    'post_init_hook': 'post_hide_default_menus',

}

