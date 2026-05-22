# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
import json
import base64
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

class CoreAppExportImport(models.TransientModel):
    _name = 'core.app.export.import'
    _description = 'Core App Export/Import Wizard'

    operation = fields.Selection([
        ('export', 'Export'),
        ('import', 'Import')
    ], string='Operation', required=True, default='export')

    # Export fields
    export_categories = fields.Boolean('Categories & Features', default=True)
    export_groups = fields.Boolean('Groups', default=True)
    export_roles = fields.Boolean('Roles', default=True)
    export_menus = fields.Boolean('Menus', default=True)
    export_users = fields.Boolean('Users', default=True)
    export_user_passwords = fields.Boolean('Include User Passwords', default=False,
        help="Warning: Passwords will be exported in plain text!")

    # Import fields
    import_file = fields.Binary('Import File', required=False)
    import_filename = fields.Char('Filename')
    import_mode = fields.Selection([
        ('create_only', 'Create Only (Skip existing)'),
        ('update_only', 'Update Only (Skip new)'),
        ('create_update', 'Create & Update')
    ], string='Import Mode', default='create_update')

    # Result fields
    export_data = fields.Binary('Export Data', readonly=True)
    export_filename = fields.Char('Export Filename', readonly=True)
    import_log = fields.Text('Import Log', readonly=True)

    def _check_admin_rights(self):
        """Kiểm tra quyền Admin"""
        if not self.env.user.has_group('CoreApp.group_CoreApp_admin') and not self.env.is_superuser():
            raise UserError("ACCESS DENIED! Only 'Core App Administrator' can export/import data.")

    # ==================== EXPORT METHODS ====================

    def action_export(self):
        """Export dữ liệu CoreApp ra file JSON"""
        self._check_admin_rights()
        
        export_data = {
            'export_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'export_by': self.env.user.name,
            'version': '1.0',
            'data': {}
        }

        # Export Categories & Features
        if self.export_categories:
            export_data['data']['categories'] = self._export_categories()

        # Export Groups
        if self.export_groups:
            export_data['data']['groups'] = self._export_groups()

        # Export Roles
        if self.export_roles:
            export_data['data']['roles'] = self._export_roles()

        # Export Menus
        if self.export_menus:
            export_data['data']['menus'] = self._export_menus()

        # Export Users
        if self.export_users:
            export_data['data']['users'] = self._export_users()

        # Tạo file JSON
        json_data = json.dumps(export_data, indent=2, ensure_ascii=False)
        encoded_data = base64.b64encode(json_data.encode('utf-8'))
        
        filename = f"CoreApp_Export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        self.write({
            'export_data': encoded_data,
            'export_filename': filename
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'core.app.export.import',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'show_export_result': True}
        }

    def _export_categories(self):
        """Export Categories và Features"""
        categories = []
        
        # Lấy tất cả categories thuộc CoreApp
        category_records = self.env['ir.module.category'].sudo().search([
            ('is_from_CoreApp', '=', True)
        ], order='parent_id, name')

        for cat in category_records:
            cat_data = {
                'id': cat.id,
                'name': cat.name,
                'description': cat.description or '',
                'parent_id': cat.parent_id.id if cat.parent_id else None,
                'parent_name': cat.parent_id.name if cat.parent_id else None,
                'is_from_CoreApp': True
            }
            
            # Chỉ thêm sequence nếu field tồn tại
            if hasattr(cat, 'sequence'):
                cat_data['sequence'] = cat.sequence
                
            categories.append(cat_data)

        return categories

    def _export_groups(self):
        """Export Groups"""
        groups = []
        
        group_records = self.env['res.groups'].sudo().search([
            ('category_id.is_from_CoreApp', '=', True)
        ], order='category_id, name')

        for group in group_records:
            groups.append({
                'id': group.id,
                'name': group.name,
                'category_id': group.category_id.id,
                'category_name': group.category_id.name,
                'implied_ids': [g.id for g in group.implied_ids],
                'implied_names': [g.name for g in group.implied_ids],
                'is_from_CoreApp': group.is_from_CoreApp
            })

        return groups

    def _export_roles(self):
        """Export Roles"""
        roles = []
        
        role_records = self.env['core.role'].sudo().search([], order='name')

        for role in role_records:
            roles.append({
                'id': role.id,
                'name': role.name,
                'group_ids': [g.id for g in role.group_ids],
                'group_names': [g.name for g in role.group_ids]
            })

        return roles

    def _export_menus(self):
        """Export Menus"""
        menus = []
        
        menu_records = self.env['core.menu'].sudo().search([], order='parent_id, sequence')

        for menu in menu_records:
            menu_data = {
                'id': menu.id,
                'name': menu.name,
                'sequence': menu.sequence,
                'active': menu.active,
                'parent_id': menu.parent_id.id if menu.parent_id else None,
                'parent_name': menu.parent_id.name if menu.parent_id else None,
                'target_menu_id': menu.target_menu_id.id if menu.target_menu_id else None,
                'target_menu_xmlid': self._get_menu_xmlid(menu.target_menu_id) if menu.target_menu_id else None,
                'target_menu_name': menu.target_menu_id.complete_name if menu.target_menu_id else None,
                'web_icon_data': menu.web_icon_data.decode('utf-8') if menu.web_icon_data else None,
                'role_ids': [r.id for r in menu.role_ids],
                'role_names': [r.name for r in menu.role_ids],
                'inherit_groups': menu.inherit_groups
            }
            menus.append(menu_data)

        return menus
    
    def _get_menu_xmlid(self, menu):
        """Lấy XML ID của menu để import chính xác hơn"""
        if not menu:
            return None
        IrModelData = self.env['ir.model.data'].sudo()
        data = IrModelData.search([
            ('model', '=', 'ir.ui.menu'),
            ('res_id', '=', menu.id)
        ], limit=1)
        if data:
            return f"{data.module}.{data.name}"
        return None

    def _export_users(self):
        """Export Users"""
        users = []
        
        user_records = self.env['res.users'].sudo().search([
            ('is_from_CoreApp', '=', True)
        ], order='name')

        for user in user_records:
            user_data = {
                'id': user.id,
                'name': user.name,
                'login': user.login,
                'email': user.email or '',
                'active': user.active,
                'lang': user.lang or 'en_US',
                'core_role_id': user.core_role_id.id if user.core_role_id else None,
                'core_role_name': user.core_role_id.name if user.core_role_id else None,
                'action_id': user.action_id.id if user.action_id else None,
                'is_from_CoreApp': True
            }

            # Chỉ export password nếu user chọn
            if self.export_user_passwords:
                user_data['password'] = '***ENCRYPTED***'  # Không export password thật

            users.append(user_data)

        return users

    # ==================== IMPORT METHODS ====================

    def action_import(self):
        """Import dữ liệu từ file JSON"""
        self._check_admin_rights()
        
        if not self.import_file:
            raise UserError("Please select a file to import!")

        try:
            # Decode file
            json_data = base64.b64decode(self.import_file).decode('utf-8')
            import_data = json.loads(json_data)
            
            log = []
            log.append("=" * 50)
            log.append(f"IMPORT STARTED: {datetime.now()}")
            log.append(f"Import Mode: {dict(self._fields['import_mode'].selection).get(self.import_mode)}")
            log.append("=" * 50)

            data = import_data.get('data', {})

            # Import theo thứ tự phụ thuộc
            if 'categories' in data:
                log.extend(self._import_categories(data['categories']))

            if 'groups' in data:
                log.extend(self._import_groups(data['groups']))

            if 'roles' in data:
                log.extend(self._import_roles(data['roles']))

            if 'menus' in data:
                log.extend(self._import_menus(data['menus']))

            if 'users' in data:
                log.extend(self._import_users(data['users']))

            log.append("=" * 50)
            log.append(f"IMPORT COMPLETED: {datetime.now()}")
            log.append("=" * 50)

            self.import_log = '\n'.join(log)

            return {
                'type': 'ir.actions.act_window',
                'res_model': 'core.app.export.import',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
                'context': {'show_import_result': True}
            }

        except json.JSONDecodeError:
            raise UserError("Invalid JSON file format!")
        except Exception as e:
            raise UserError(f"Import failed: {str(e)}")

    def _import_categories(self, categories_data):
        """Import Categories"""
        log = ["\n>>> IMPORTING CATEGORIES & FEATURES"]
        Category = self.env['ir.module.category'].sudo()
        
        # Map old_id -> new_id
        id_mapping = {}
        
        # Sort: parents first
        categories_sorted = sorted(categories_data, key=lambda x: (x.get('parent_id') or 0))
        
        for cat_data in categories_sorted:
            old_id = cat_data.get('id')
            name = cat_data['name']
            
            # Tìm category hiện có
            existing = Category.search([
                ('name', '=', name),
                ('is_from_CoreApp', '=', True)
            ], limit=1)

            vals = {
                'name': name,
                'description': cat_data.get('description', ''),
                'is_from_CoreApp': True
            }
            
            # Chỉ thêm sequence nếu có trong data và field tồn tại
            if cat_data.get('sequence') is not None and 'sequence' in Category._fields:
                vals['sequence'] = cat_data.get('sequence', 10)

            # Xử lý parent_id
            if cat_data.get('parent_id'):
                new_parent_id = id_mapping.get(cat_data['parent_id'])
                if new_parent_id:
                    vals['parent_id'] = new_parent_id

            if existing:
                if self.import_mode in ['update_only', 'create_update']:
                    existing.write(vals)
                    id_mapping[old_id] = existing.id
                    log.append(f"  ✓ Updated: {name}")
                else:
                    id_mapping[old_id] = existing.id
                    log.append(f"  • Skipped: {name} (already exists)")
            else:
                if self.import_mode in ['create_only', 'create_update']:
                    new_cat = Category.create(vals)
                    id_mapping[old_id] = new_cat.id
                    log.append(f"  ✓ Created: {name}")
                else:
                    log.append(f"  • Skipped: {name} (not exists)")

        return log

    def _import_groups(self, groups_data):
        """Import Groups"""
        log = ["\n>>> IMPORTING GROUPS"]
        Group = self.env['res.groups'].sudo()
        Category = self.env['ir.module.category'].sudo()
        
        id_mapping = {}
        
        for group_data in groups_data:
            old_id = group_data.get('id')
            name = group_data['name']
            
            # Tìm category
            category = Category.search([
                ('name', '=', group_data.get('category_name')),
                ('is_from_CoreApp', '=', True)
            ], limit=1)

            if not category:
                log.append(f"  ✗ Skipped: {name} (category not found)")
                continue

            existing = Group.search([
                ('name', '=', name),
                ('category_id', '=', category.id)
            ], limit=1)

            vals = {
                'name': name,
                'category_id': category.id,
                'is_from_CoreApp': group_data.get('is_from_CoreApp', True)
            }

            if existing:
                if self.import_mode in ['update_only', 'create_update']:
                    existing.write(vals)
                    id_mapping[old_id] = existing.id
                    log.append(f"  ✓ Updated: {name}")
                else:
                    id_mapping[old_id] = existing.id
                    log.append(f"  • Skipped: {name} (already exists)")
            else:
                if self.import_mode in ['create_only', 'create_update']:
                    new_group = Group.create(vals)
                    id_mapping[old_id] = new_group.id
                    log.append(f"  ✓ Created: {name}")
                else:
                    log.append(f"  • Skipped: {name} (not exists)")

        # Update implied_ids sau khi tất cả groups đã được tạo
        for group_data in groups_data:
            if group_data.get('implied_names'):
                group_id = id_mapping.get(group_data['id'])
                if group_id:
                    implied_groups = Group.search([
                        ('name', 'in', group_data['implied_names'])
                    ])
                    if implied_groups:
                        Group.browse(group_id).write({
                            'implied_ids': [(6, 0, implied_groups.ids)]
                        })

        return log

    def _import_roles(self, roles_data):
        """Import Roles"""
        log = ["\n>>> IMPORTING ROLES"]
        Role = self.env['core.role'].sudo()
        Group = self.env['res.groups'].sudo()
        
        for role_data in roles_data:
            name = role_data['name']
            
            existing = Role.search([('name', '=', name)], limit=1)

            # Tìm groups theo tên
            group_names = role_data.get('group_names', [])
            groups = Group.search([('name', 'in', group_names)])

            vals = {
                'name': name,
                'group_ids': [(6, 0, groups.ids)]
            }

            if existing:
                if self.import_mode in ['update_only', 'create_update']:
                    existing.write(vals)
                    log.append(f"  ✓ Updated: {name}")
                else:
                    log.append(f"  • Skipped: {name} (already exists)")
            else:
                if self.import_mode in ['create_only', 'create_update']:
                    Role.create(vals)
                    log.append(f"  ✓ Created: {name}")
                else:
                    log.append(f"  • Skipped: {name} (not exists)")

        return log

    def _import_menus(self, menus_data):
        """Import Menus"""
        log = ["\n>>> IMPORTING MENUS"]
        Menu = self.env['core.menu'].sudo()
        Role = self.env['core.role'].sudo()
        IrMenu = self.env['ir.ui.menu'].sudo()
        
        id_mapping = {}
        
        # Sort: parents first
        menus_sorted = sorted(menus_data, key=lambda x: (x.get('parent_id') or 0))
        
        for menu_data in menus_sorted:
            old_id = menu_data.get('id')
            name = menu_data['name']
            
            existing = Menu.search([('name', '=', name)], limit=1)

            vals = {
                'name': name,
                'sequence': menu_data.get('sequence', 10),
                'active': menu_data.get('active', True),
                'inherit_groups': menu_data.get('inherit_groups', True)
            }

            # Parent
            if menu_data.get('parent_id'):
                new_parent_id = id_mapping.get(menu_data['parent_id'])
                if new_parent_id:
                    vals['parent_id'] = new_parent_id

            # Target menu - Cải thiện logic tìm kiếm
            target_menu = None
            
            # Phương pháp 1: Tìm theo XML ID (chính xác nhất)
            if menu_data.get('target_menu_xmlid'):
                try:
                    target_menu = self.env.ref(menu_data['target_menu_xmlid'], raise_if_not_found=False)
                    if target_menu:
                        log.append(f"    → Found target menu by XML ID: {menu_data['target_menu_xmlid']}")
                except:
                    pass
            
            # Phương pháp 2: Tìm theo complete_name
            if not target_menu and menu_data.get('target_menu_name'):
                target_menu = IrMenu.search([
                    ('complete_name', '=', menu_data['target_menu_name'])
                ], limit=1)
                if target_menu:
                    log.append(f"    → Found target menu by complete name: {menu_data['target_menu_name']}")
            
            # Phương pháp 3: Tìm theo name (phần cuối của complete_name)
            if not target_menu and menu_data.get('target_menu_name'):
                menu_name_parts = menu_data['target_menu_name'].split(' / ')
                if menu_name_parts:
                    last_part = menu_name_parts[-1]
                    target_menu = IrMenu.search([
                        ('name', '=', last_part)
                    ], limit=1)
                    if target_menu:
                        log.append(f"    → Found target menu by name: {last_part}")
            
            if target_menu:
                vals['target_menu_id'] = target_menu.id
            elif menu_data.get('target_menu_name'):
                log.append(f"    ⚠ Warning: Target menu not found: {menu_data['target_menu_name']}")

            # Roles
            if menu_data.get('role_names'):
                roles = Role.search([('name', 'in', menu_data['role_names'])])
                vals['role_ids'] = [(6, 0, roles.ids)]

            # Icon data
            if menu_data.get('web_icon_data'):
                try:
                    vals['web_icon_data'] = menu_data['web_icon_data'].encode('utf-8')
                except:
                    log.append(f"    ⚠ Warning: Could not encode icon data for {name}")

            if existing:
                if self.import_mode in ['update_only', 'create_update']:
                    existing.write(vals)
                    id_mapping[old_id] = existing.id
                    log.append(f"  ✓ Updated: {name}")
                else:
                    id_mapping[old_id] = existing.id
                    log.append(f"  • Skipped: {name} (already exists)")
            else:
                if self.import_mode in ['create_only', 'create_update']:
                    new_menu = Menu.create(vals)
                    id_mapping[old_id] = new_menu.id
                    log.append(f"  ✓ Created: {name}")
                else:
                    log.append(f"  • Skipped: {name} (not exists)")

        return log

    def _import_users(self, users_data):
        """Import Users"""
        log = ["\n>>> IMPORTING USERS"]
        User = self.env['res.users'].sudo()
        Role = self.env['core.role'].sudo()
        
        for user_data in users_data:
            login = user_data['login']
            name = user_data['name']
            
            existing = User.search([('login', '=', login)], limit=1)

            vals = {
                'name': name,
                'login': login,
                'email': user_data.get('email', login),
                'active': user_data.get('active', True),
                'lang': user_data.get('lang', 'en_US'),
                'is_from_CoreApp': True
            }

            # Role
            if user_data.get('core_role_name'):
                role = Role.search([('name', '=', user_data['core_role_name'])], limit=1)
                if role:
                    vals['core_role_id'] = role.id

            if existing:
                if self.import_mode in ['update_only', 'create_update']:
                    # Không update password khi import
                    existing.write(vals)
                    log.append(f"  ✓ Updated: {name} ({login})")
                else:
                    log.append(f"  • Skipped: {name} ({login}) - already exists")
            else:
                if self.import_mode in ['create_only', 'create_update']:
                    # Tạo user mới với password mặc định
                    vals['password'] = 'admin123'  # Password mặc định
                    User.create(vals)
                    log.append(f"  ✓ Created: {name} ({login}) - Default password: admin123")
                else:
                    log.append(f"  • Skipped: {name} ({login}) - not exists")

        return log