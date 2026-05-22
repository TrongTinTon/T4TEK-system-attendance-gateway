from odoo import api, SUPERUSER_ID

def post_hide_default_menus(env):
    hidden_group = env.ref('CoreApp.group_core_odoo', raise_if_not_found=False)
    if not hidden_group:
        return

    Menu = env['ir.ui.menu']

    # Chỉ lấy menu root (trừ Settings hay tùy bạn muốn ngoại lệ)
    root_menus = Menu.search([('parent_id', '=', False)])
    

    for root in root_menus:
        if hidden_group in root.group_ids:
            continue
        # 1. Lấy group quyền gốc của root (nếu có)
        root_groups = root.group_ids.ids

        # 2. Lấy submenu cấp 1
        level1_submenus = Menu.search([('parent_id', '=', root.id)])

        for sub in level1_submenus:
            # Chỉ gán group từ root nếu submenu chưa có group
            if not sub.group_ids:
                if root_groups:  # root có group thì mới gán
                    sub.write({
                        'group_ids': [(6, 0, root_groups)]
                    })

        # 3. Cuối cùng gán group hidden cho root
        root.write({
            'group_ids': [(6, 0, [hidden_group.id])]
        })
