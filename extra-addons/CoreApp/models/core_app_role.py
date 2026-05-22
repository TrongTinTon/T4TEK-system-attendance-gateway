# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)

class CoreApp_Role(models.Model):
    _name = 'core.role'
    _description = 'Core App Role'
    _order = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    name = fields.Char(string='Roles', required=True, tracking=True)
    home_menu_id = fields.Many2one(
        'ir.ui.menu', 
        string='Menu mặc định',
        tracking=True,
        help="Chọn menu khởi động cho vai trò này"
    )

    # Field kỹ thuật (vẫn cần thiết để hệ thống chạy, nhưng sẽ ẩn đi hoặc read-only)
    action_id = fields.Many2one(
        'ir.actions.actions', 
        string='Action ID (System)',
        compute='_compute_action_from_menu',
        store=True, # Lưu vào DB để sync xuống user
        readonly=False # Để có thể sửa thủ công nếu cần thiết (optional)
    )

    group_ids = fields.Many2many(
        'res.groups',
        string='Groups',
        tracking=True
    )

    @api.depends('home_menu_id')
    def _compute_action_from_menu(self):
        for role in self:
            if role.home_menu_id and role.home_menu_id.action:
                # Lấy ID của action gắn với menu đó
                # Lưu ý: menu.action trả về record action, ta lấy .id
                role.action_id = role.home_menu_id.action.id
            else:
                role.action_id = False
    @api.model
    def _get_internal_user_group_id(self):
        """ Helper để lấy ID của nhóm Internal User """
        internal_user_group = self.env.ref('base.group_user', raise_if_not_found=False)
        return internal_user_group.id if internal_user_group else None

    def _sync_users_from_role(self):
        odoobot_id = self.env['res.users']._get_odoobot_id()
        for role in self:
            # Tìm tất cả người dùng có vai trò này trong core_role_ids
            affected_users = self.env['res.users'].search([
                '|',
                ('core_role_id', '=', role.id),
                ('core_role_ids', 'in', [role.id])
            ])

            for user in affected_users:
                group_ids = user._get_aggregated_groups()
                groups_field = 'group_ids' if 'group_ids' in user._fields else 'groups_id'
                vals_update = {
                    groups_field: [fields.Command.set(group_ids)]
                }
                
                # Cập nhật action_id nếu cần (fallback logi)
                if not user.action_id and role.action_id:
                    vals_update['action_id'] = role.action_id.id
                
                user.with_user(odoobot_id).sudo().write(vals_update)

    @api.model
    def create(self, vals):
        """ 
        Override hàm create để mặc định thêm group CoreApp Access 
        ngay khi bản ghi được tạo.
        """
        # 1. Lấy các nhóm quyền bắt buộc
        guest_group = self.env.ref('CoreApp.group_CoreApp_access', raise_if_not_found=False)
        # internal_group = self.env.ref('base.group_user', raise_if_not_found=False)

        # 2. Xử lý cả trường hợp vals là dict (single) hoặc list (batch)
        if isinstance(vals, dict):
            vals_list = [vals]
        else:
            vals_list = vals

        for v in vals_list:
            if 'group_ids' not in v:
                v['group_ids'] = []

        # 3. Tạo bản ghi
        role = super(CoreApp_Role, self).create(vals)

        # 5. Đồng bộ user nếu cần thiết
        role._sync_users_from_role()
        
        return role

    def write(self, vals):
        """ 
        Override write để đồng bộ user khi group_ids thay đổi 
        và đảm bảo quyền bắt buộc không bị xóa.
        """
        res = super(CoreApp_Role, self).write(vals)

        # Nếu đang sửa đổi group_ids, ta kiểm tra xem có bị mất quyền bắt buộc không
        if 'group_ids' in vals:
            guest_group = self.env.ref('CoreApp.group_CoreApp_access', raise_if_not_found=False)
            internal_group = self.env.ref('base.group_user', raise_if_not_found=False)
            
            for role in self:
                groups_to_add = []
                # Kiểm tra và thêm lại nếu thiếu (Enforce consistency)
                # if internal_group and internal_group not in role.group_ids:
                #     groups_to_add.append(internal_group.id)
                
                if guest_group and guest_group not in role.group_ids:
                    groups_to_add.append(guest_group.id)
                
                if groups_to_add:
                    # Gọi super write để tránh lặp vô tận (recursion)
                    super(CoreApp_Role, role).write({
                        'group_ids': [(4, gid) for gid in groups_to_add]
                    })

            # Sau khi đảm bảo quyền ở Role ok, mới sync xuống User
        should_sync = 'group_ids' in vals or 'home_menu_id' in vals or 'action_id' in vals
        
        if should_sync:
            self._sync_users_from_role()

        return res
    
    @api.onchange('group_ids')
    def _onchange_filter_menus_by_permission(self):
        # Điều kiện cơ bản: Phải là menu lá (có action)
        domain = [
            ('action', '!=', False),          # Chỉ lấy menu lá
            ('is_core_app_menu', '=', True),  # Chỉ lấy menu được đánh dấu
        ]

        if self.group_ids:
            # Logic: 
            # 1. Menu không yêu cầu quyền cụ thể (group_ids = False)
            # HOẶC
            # 2. Menu yêu cầu quyền nằm trong danh sách quyền của Role (group_ids in ...)
            domain += [
                '|',
                ('group_ids', '=', False),
                ('group_ids', 'in', self.group_ids.ids)
            ]
        else:
            # Nếu Role chưa chọn group nào: Chỉ hiện menu public (không set quyền)
            domain += [('group_ids', '=', False)]

        # Tìm danh sách ID menu thỏa mãn
        valid_menus = self.env['ir.ui.menu'].search(domain)

        # Trả về domain giới hạn danh sách được chọn
        return {'domain': {'home_menu_id': [('id', 'in', valid_menus.ids)]}}