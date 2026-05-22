# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.exceptions import AccessError

class CoreApp_ResGroups(models.Model):
    _name = 'res.groups'
    _inherit = ['res.groups', 'mail.thread']
    
    name = fields.Char(tracking=True)
    implied_ids = fields.Many2many(tracking=True)

    category_id = fields.Many2one(
        'ir.module.category', 
        string='Category', 
        ondelete='restrict',
        tracking=True,
        help="The category grouping the related groups."
    )

   
    is_from_CoreApp = fields.Boolean(string="From Core App", default=False, help="Check if the group is created by Core App module")


    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        """
        Override hàm get_view để chặn truy cập giao diện
        """
        #Gọi hàm gốc để lấy view trước
        res = super().get_view(view_id, view_type, **options)

        # Kiểm tra Nếu đang load view dạng 'list'hoặc 'form'
        if view_type in ['list', 'form', 'kanban']:
            user = self.env.user
            is_admin = user.has_group('CoreApp.group_CoreApp_admin') or self.env.is_superuser()
            
            if not is_admin:
                is_selecting_for_role = self.env.context.get('core_app_allow_select_group')
                if is_selecting_for_role:
                    return res
                try:
                     restricted_views = [
                        self.env.ref('CoreApp.CoreApp_group_view_list').id,
                        self.env.ref('CoreApp.CoreApp_group_view_form').id,
                        self.env.ref('CoreApp.CoreApp_group_view_form_readonly').id
                    ]
                except ValueError:
                    restricted_views = []

                if view_id in restricted_views:
                    raise AccessError("⚠️ ACCESS DENIED\nYou don't any authoritiess to access this view (Groups).")

        return res

    def _check_CoreApp_security(self):
        """
        Hàm này đảm bảo chỉ có Core App Admin hoặc Superuser
        mới được phép can thiệp vào dữ liệu của Core App.
        """
        # Nếu là Superuser (OdooBot) thì cho qua
        if self.env.is_superuser():
            return

        # Nếu người dùng KHÔNG có group Admin
        if not self.env.user.has_group('CoreApp.group_CoreApp_admin'):
            # Chặn ngay lập tức
            raise AccessError("ACCESS DENIED! Only 'Core App Administrator' is allowed to create/edit/delete Groups.")


    @api.model
    def _get_odoobot_id(self):
        """
        hàm để lấy ID của OdooBot
        """
        try:
            return self.env.ref('base.user_root').id
        except ValueError:
            return self.env.ref('base.user_admin').id

    @api.model
    def create(self, vals):
        """
        Override hàm create để dùng sudo() với user Odoobot.
        """
        

        is_admin = self.env.user.has_group('CoreApp.group_CoreApp_admin') or self.env.is_superuser()


        if not is_admin:
            # Check cả trong vals (dữ liệu gửi lên) VÀ context (giá trị mặc định)
            is_CoreApp = vals.get('is_from_CoreApp') or self.env.context.get('default_is_from_CoreApp')
            
            if is_CoreApp:
                raise UserError("YOU DON'T HAVE RIGHTS:\nOnly 'Core App Administrator' is allowed to create.")
            
            return super(CoreApp_ResGroups, self).create(vals)
        odoobot_id = self._get_odoobot_id()
        
        # cấp quyền thực thi tạo group bằng lệnh sudo
        group_sudo = super(CoreApp_ResGroups, self.with_user(odoobot_id).sudo()).create(vals)
        # Trả về record của user hiện tại (bỏ sudo)
        return self.browse(group_sudo.id)

    def write(self, vals):
        """
        Override hàm write để dùng sudo() với user Odoobot.
        """

        if any(rec.is_from_CoreApp for rec in self):
            self._check_CoreApp_security()

        odoobot_id = self._get_odoobot_id()

        # cấp quyền thực thi write với lệnh sudo
        res = super(CoreApp_ResGroups, self.with_user(odoobot_id).sudo()).write(vals)

        if not vals:
            return res  # nếu không sửa đổi, bỏ qua
        
        # 'self' là các bản ghi res.groups đang được write.
        roles_to_update = self.env['core.role'].search([
            ('group_ids', 'in', self.ids)
        ])

        if not roles_to_update:
            return res
        
        # Hàm này sẽ tự động cập nhật tất cả người dùng thuộc các group quyền được sửa đổi
        roles_to_update._sync_users_from_role()
        return res

    def unlink(self):

        if any(rec.is_from_CoreApp for rec in self):
            self._check_CoreApp_security()

        roles_to_update = self.env['core.role'].search([
            ('group_ids', 'in', self.ids)
        ])
        odoobot_id = self._get_odoobot_id()

        # cấp quyền thực thi delete với lệnh sudo()
        res = super(CoreApp_ResGroups, self.with_user(odoobot_id).sudo()).unlink()
        if roles_to_update:
            roles_to_update._sync_users_from_role()
        return res
    
class CoreApp_IrModuleCategory(models.Model):
    _name = 'ir.module.category'
    
    # 2. Kế thừa mail.thread
    _inherit = ['ir.module.category', 'mail.thread']

    # 3. Tracking tên Category
    name = fields.Char(tracking=True)
    parent_id = fields.Many2one(
        'ir.module.category', 
        string='Parent Category', 
        index=True, 
        tracking=True,
        ondelete='restrict'
    )

    is_from_CoreApp = fields.Boolean(string="From Core App", default=False, help="Check if the category is created by Core App module")

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        """
        Override hàm get_view để chặn truy cập giao diện
        """
        #Gọi hàm gốc để lấy view trước
        res = super().get_view(view_id, view_type, **options)

        # Kiểm tra Nếu đang load view dạng 'list'hoặc 'form'
        if view_type in ['list', 'form', 'kanban']:
            user = self.env.user
            is_admin = user.has_group('CoreApp.group_CoreApp_admin') or self.env.is_superuser()
            
            if not is_admin:
                is_selecting_for_role = self.env.context.get('core_app_allow_select_group')
                if is_selecting_for_role:
                    return res
                try:
                     restricted_views = [
                        self.env.ref('CoreApp.CoreApp_ir_module_category_view_list').id,
                        self.env.ref('CoreApp.CoreApp_ir_module_category_view_form_app').id,
                        self.env.ref('CoreApp.CoreApp_ir_module_category_view_form_feature').id
                    ]
                except ValueError:
                    restricted_views = []

                if view_id in restricted_views:
                    raise AccessError("⚠️ ACCESS DENIED\nYou don't any authoritiess to access this view (Groups).")

        return res


    def _check_CoreApp_security(self):
        """
        Hàm này đảm bảo chỉ có Core App Admin hoặc Superuser
        mới được phép can thiệp vào dữ liệu của Core App.
        """
        # Nếu là Superuser (OdooBot) thì cho qua
        if self.env.is_superuser():
            return

        # Nếu người dùng KHÔNG có group Admin
        if not self.env.user.has_group('CoreApp.group_CoreApp_admin'):
            # Chặn ngay lập tức
            raise AccessError("ACCESS DENIED! Only 'Core App Administrator' is allowed to create/edit/delete Categories.")
    @api.model
    def _get_odoobot_id(self):
        """
        hàm để lấy ID của OdooBot (người dùng hệ thống, thường là ID=1).
        """
        try:
            return self.env.ref('base.user_root').id
        except ValueError:
            return self.env.ref('base.user_admin').id

    @api.model
    def create(self, vals):
        """
        override hàm create để dùng sudo() với user Odoobot.
        """

        is_admin = self.env.user.has_group('CoreApp.group_CoreApp_admin') or self.env.is_superuser()


        if not is_admin:
            # Check cả trong vals (dữ liệu gửi lên) VÀ context (giá trị mặc định)
            is_CoreApp = vals.get('is_from_CoreApp') or self.env.context.get('default_is_from_CoreApp')
            
            if is_CoreApp:
                raise UserError("YOU DON'T HAVE RIGHTS:\nOnly 'Core App Administrator' is allowed to create.")
            
            return super(CoreApp_IrModuleCategory, self).create(vals)

        odoobot_id = self._get_odoobot_id()
        
        # TẠO CATEGORY VỚI QUYỀN SUDO CỦA ODOOBOT
        category_sudo = super(CoreApp_IrModuleCategory, self.with_user(odoobot_id).sudo()).create(vals)
        # Trả về bản ghi của user hiện tại (bỏ sudo)
        return self.browse(category_sudo.id)

    def write(self, vals):
        """
        Override hàm write để dùng sudo() với user Odoobot.
        """

        if any(rec.is_from_CoreApp for rec in self):
            self._check_CoreApp_security()
        odoobot_id = self._get_odoobot_id()

        # update category
        res = super(CoreApp_IrModuleCategory, self.with_user(odoobot_id).sudo()).write(vals)
        
        return res
    def unlink(self):
        """
        Hàm xóa kiểm tra các categories trước khi xóa và sử dụng sudo quyền để xóa
        """
        if any(rec.is_from_CoreApp for rec in self):
            self._check_CoreApp_security()

        for category in self:
            # Kiểm tra feature
            child_features = self.env['ir.module.category'].search([
                ('parent_id', '=', category.id)
            ], limit=1)

            # Kiểm tra group quyền
            related_groups = self.env['res.groups'].search([
                ('category_id', '=', category.id)
            ], limit=1)

            # Nếu có 1 trong 2, thông báo lỗi
            if child_features or related_groups:
                error_parts = []
                if child_features:
                    error_parts.append("'Features' con")
                if related_groups:
                    error_parts.append("'Groups'")
                
                raise UserError(
                    "You can't delete Categories '%s'. \n"
                    "There still %s attach to it. Please delete it or put it in another Categories."
                    % (category.name, " và ".join(error_parts))
                )
                

        # tiến hành xóa bằng quyền sudo nếu không có lỗi
        odoobot_id = self._get_odoobot_id()
        res = super(CoreApp_IrModuleCategory, self.with_user(odoobot_id).sudo()).unlink()
        
        return res