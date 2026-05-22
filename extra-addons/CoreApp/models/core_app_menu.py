from odoo import models, fields, api
from odoo.exceptions import UserError
import logging


_logger = logging.getLogger(__name__)

class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    # Field đánh dấu, mặc định là False
    is_core_app_menu = fields.Boolean(string="Is Core App Menu", default=False, index=True)

    @api.model
    def action_hide_new_installed_menus(self):
        """Hàm quét và ẩn các root menu mới cài đặt"""
        try:
            hidden_group = self.env.ref('CoreApp.group_core_odoo', raise_if_not_found=False)
            if not hidden_group:
                _logger.warning("CoreApp: group_core_odoo not found, skipping hide menus")
                return

            # Chỉ lấy menu root
            root_menus = self.search([('parent_id', '=', False)])

            for root in root_menus:
                # Nếu menu này đã bị ẩn rồi thì continue
                if hidden_group in root.group_ids:
                    continue

                # Lấy group quyền gốc của root
                root_groups = root.group_ids.ids

                # Lấy submenu cấp 1
                level1_submenus = self.search([('parent_id', '=', root.id)])

                for sub in level1_submenus:
                    # Chỉ gán group từ root nếu submenu chưa có group
                    if not sub.group_ids:
                        if root_groups:  # root có group thì mới gán
                            sub.write({
                                'group_ids': [(6, 0, root_groups)]
                            })

                # gán group hidden cho root
                root.write({
                    'group_ids': [(6, 0, [hidden_group.id])]
                })
        except Exception as e:
            _logger.error("CoreApp: action_hide_new_installed_menus failed: %s", e, exc_info=True)

class CoreApp_Menu(models.Model):
    _name = "core.menu"
    _description = "Core Menu Management"
    _rec_name = "name"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char("Menu Name", required=True, tracking=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    # Đảm bảo attachment=False để lưu vào DB column
    web_icon_data = fields.Binary(string="Web Icon Image",attachment=False)

    parent_id = fields.Many2one("core.menu", string="Parent Menu", ondelete="cascade")
    child_ids = fields.One2many("core.menu", "parent_id", string="Child Menus")

    ir_menu_id = fields.Many2one("ir.ui.menu", string="Linked Menu", readonly=True)
    target_menu_id = fields.Many2one(
        "ir.ui.menu",
        string="Target Menu",
        context={'ir.ui.menu.full_list': True},
        domain="[('is_core_app_menu', '=', False)]",
        tracking=True
    )

    role_ids = fields.Many2many("core.role", "core_menu_role_rel", "menu_id", "role_id", string="Allowed Roles", context={'no_create': True}, tracking=True)
    inherit_groups = fields.Boolean(default=True)
    show_ir_menu = fields.Boolean(string="Show Linked Menu ID", default=False)

    @api.model
    def create(self, vals):
        rec = super().create(vals)
        # Lấy dữ liệu ảnh TƯƠI SỐNG trực tiếp từ vals
        # Nếu không có trong vals thì mới lấy từ rec
        rec._create_ir_menu()
        return rec

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            rec._create_ir_menu()
        return res
    
    def unlink(self):
        for rec in self:
            if rec.child_ids:
                raise UserError("You must delete all child menus before deleting parent menu")
            if rec.ir_menu_id:
                rec.ir_menu_id.sudo().unlink()
        return super(CoreApp_Menu, self.sudo()).unlink()

    def _create_ir_menu(self, new_icon_data=None):
        """
        1. Phân quyền: Role thì theo Role, không thì mặc định.
        2. Tên menu: CƯỠNG ÉP đồng bộ tên này cho TẤT CẢ ngôn ngữ đang cài đặt.
        3. Icon: Xử lý ảnh.
        """
        admin_env = self.sudo().env
        IrMenu = admin_env["ir.ui.menu"]
        ResLang = admin_env["res.lang"] # Gọi thêm model ngôn ngữ
        
        admin_group = admin_env.ref("base.group_system")
        core_user_group = admin_env.ref("CoreApp.group_CoreApp_access")

        # Lấy danh sách mã của tất cả ngôn ngữ đang kích hoạt trong hệ thống (vd: ['en_US', 'vi_VN'])
        active_lang_codes = ResLang.search([]).mapped('code')

        for rec in self:
            # --- 1. LOGIC GROUPS
            groups_set = set()
            if rec.role_ids:
                # 1. Lấy tất cả group nằm trong Role
                role_groups = rec.role_ids.sudo().mapped('group_ids')
                groups_set.update(role_groups.ids)
                
                # 2. BƯỚC QUAN TRỌNG: Nếu có group CoreApp trong list này -> ĐÁ NÓ RA
                if core_user_group.id in groups_set:
                    groups_set.remove(core_user_group.id)
            else:
                if rec.target_menu_id and rec.target_menu_id.group_ids:
                    target_groups = rec.target_menu_id.group_ids
                    groups_set.update(target_groups.ids)
                else: groups_set.add(core_user_group.id)

            if admin_group.id not in groups_set:
                groups_set.add(admin_group.id)
            
            groups_value = [(6, 0, groups_set)]

            # --- 2. CHUẨN BỊ VALS CƠ BẢN ---
            final_icon_data = False
            if rec.web_icon_data:
                if isinstance(rec.web_icon_data, bytes):
                    final_icon_data = rec.web_icon_data.decode('utf-8')
                else:
                    final_icon_data = rec.web_icon_data

            parent_ir_menu = rec.parent_id.sudo().ir_menu_id if rec.parent_id else False
            
            action_value = False
            if rec.target_menu_id and rec.target_menu_id.action:
                action_value = f"{rec.target_menu_id.action._name},{rec.target_menu_id.action.id}"

            vals = {
                "sequence": rec.sequence,
                "active": rec.active,
                "parent_id": parent_ir_menu.id if parent_ir_menu else False,
                "action": action_value,
                "group_ids": groups_value,
                "is_core_app_menu": True,
                "web_icon_data": final_icon_data,
            }

            if rec.ir_menu_id:
                ir_menu = rec.ir_menu_id.sudo()
                ir_menu.write(vals)
            else:
                # Khi create bắt buộc phải có name, ta lấy tạm name hiện tại
                vals['name'] = rec.name
                ir_menu = IrMenu.sudo().create(vals)
                rec.sudo().write({"ir_menu_id": ir_menu.id})

            # --- 4. CƯỠNG ÉP ĐỒNG BỘ TÊN (THEO YÊU CẦU CỦA BẠN) ---
            # Logic: Duyệt qua từng ngôn ngữ -> Switch context -> Ghi đè tên
            # Điều này đảm bảo dù user đang dùng tiếng Anh hay Việt, tên vẫn y hệt nhau.
            if rec.name:
                for lang_code in active_lang_codes:
                    ir_menu.with_context(lang=lang_code).write({'name': rec.name})

            # --- 6. ĐỆ QUY ---
            if rec.child_ids:
                rec.child_ids._create_ir_menu()