# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError, AccessError

class CoreApp_ResUsers(models.Model):
    _name = 'res.users'
    _inherit = ['res.users', 'mail.thread']
    core_role_id = fields.Many2many('core.role', 'res_users_core_role_main_rel', 'user_id', 'role_id', string='Role chính (Legacy)', tracking=True)
    core_role_ids = fields.Many2many('core.role', 'res_users_core_role_rel', 'user_id', 'role_id', string='Roles', tracking=True)
    name = fields.Char(tracking=True)
    login = fields.Char(tracking=True)
    is_from_CoreApp = fields.Boolean(
        string="From Core App", 
        default=False, 
        help="Đánh dấu user này được tạo từ Core App"
    )

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        """
        Chặn người dùng không phận sự truy cập vào VIEW RÚT GỌN của Core App.
        """
        # 1. Gọi hàm gốc trước để lấy view trước
        res = super(CoreApp_ResUsers, self).get_view(view_id, view_type, **options)

        user = self.env.user
        is_core_app_member = user.has_group('CoreApp.group_CoreApp_user') or self.env.is_superuser()

        if not is_core_app_member:
            
            # Lấy ID của 2 view simplified
            # Dùng try-except để tránh lỗi nếu lỡ view chưa được load kịp
            try:
                simplified_list_id = self.env.ref('CoreApp.CoreApp_simplified_view_list').id
                simplified_form_id = self.env.ref('CoreApp.CoreApp_simplified_view_form').id
            except ValueError:
                simplified_list_id = None
                simplified_form_id = None

            # - Nếu họ cố tình mở đúng cái View ID rút gọn (Hack URL view_id=...)
            # - HOẶC nếu context có cờ 'default_is_from_CoreApp'
            is_trying_access_restricted_view = (view_id in [simplified_list_id, simplified_form_id])
            is_accessing_via_core_app_menu = self.env.context.get('default_is_from_CoreApp')

            if is_trying_access_restricted_view or is_accessing_via_core_app_menu:
                raise AccessError("⚠️ ACCESS DENIED\nYou don't have the authorities to access Core app User.")

        return res

    @api.model
    def _get_odoobot_id(self):
        """
        Helper để lấy ID của OdooBot
        """
        try:
            # base.user_root là OdooBot (ID=1)
            return self.env.ref('base.user_root').id
        except ValueError:
            # nếu không tìm thấy user_root, thì dùng user Admin (ID=2)
            return self.env.ref('base.user_admin').id

    def _get_aggregated_groups(self, role_ids=None):
        """
        Thu thập tất cả group_ids từ cả core_role_id (Legacy) và core_role_ids (M2M).
        """
        if role_ids is None:
            # Union of both fields to ensure all permissions are collected
            role_ids = list(set(self.core_role_ids.ids) | set(self.core_role_id.ids))
        
        roles = self.env['core.role'].browse(role_ids)
        all_group_ids = set()
        for role in roles:
            all_group_ids.update(role.group_ids.ids)
            
        # Thêm các nhóm bắt buộc
        internal_user_group = self.env.ref('base.group_user', raise_if_not_found=False)
        if internal_user_group:
            all_group_ids.add(internal_user_group.id)
            
        guest_group = self.env.ref('CoreApp.group_CoreApp_access', raise_if_not_found=False)
        if guest_group:
            all_group_ids.add(guest_group.id)
            
        return list(all_group_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('email') and not vals.get('login'):
                vals['login'] = vals['email']
            elif vals.get('login') and not vals.get('email'):
                vals['email'] = vals['login']
            if 'password' in vals and not vals['password']:
                vals.pop('password')

        odoobot_id = self._get_odoobot_id()

        users = super(CoreApp_ResUsers, self.with_user(odoobot_id).sudo()).create(vals_list)

        for user in users:
            if user.core_role_id or user.core_role_ids:
                group_ids = user._get_aggregated_groups()
                
                groups_field = 'group_ids' if 'group_ids' in user._fields else 'groups_id'
                user.with_user(odoobot_id).sudo().write({
                    groups_field: [fields.Command.set(group_ids)],
                })
                # Ưu tiên lấy Action ID khởi động từ Role Chính trước, nếu không có mới lấy Role Phụ
                primary_role = (user.core_role_id and user.core_role_id[0]) or (user.core_role_ids and user.core_role_ids[0]) or False
                if primary_role and primary_role.action_id:
                    user.with_user(odoobot_id).sudo().write({
                        'action_id': primary_role.action_id.id
                    })

        return users

    def write(self, vals):
        if vals.get('login') and 'email' not in vals:
            vals['email'] = vals.get('login')
        elif 'email' in vals and not vals.get('login'):
            vals['login'] = vals['email']


        need_sudo = 'groups_id' in vals or 'group_ids' in vals or 'active' in vals or 'action_id' in vals
        odoobot_id = self._get_odoobot_id()
        if need_sudo:
            res = super(CoreApp_ResUsers, self.with_user(odoobot_id).sudo()).write(vals)
        else:
            res = super(CoreApp_ResUsers, self).write(vals)

        # Nếu có sự thay đổi về Role (chính HOẶC phụ), tính toán lại toàn bộ quyền
        if 'core_role_id' in vals or 'core_role_ids' in vals:
            for user in self:
                try:
                    if user.id in [self.env.ref('base.user_root').id, self.env.ref('base.user_admin').id]:
                        continue
                except Exception:
                    pass

                group_ids = user._get_aggregated_groups()
                groups_field = 'group_ids' if 'group_ids' in user._fields else 'groups_id'
                super(CoreApp_ResUsers, user.with_user(odoobot_id).sudo()).write({
                    groups_field: [fields.Command.set(group_ids)]
                })
                
                # Cập nhật lại Action khởi động
                primary_role = (user.core_role_id and user.core_role_id[0]) or (user.core_role_ids and user.core_role_ids[0]) or False
                if primary_role and primary_role.action_id:
                    super(CoreApp_ResUsers, user.with_user(odoobot_id).sudo()).write({
                        'action_id': primary_role.action_id.id
                    })

        return res