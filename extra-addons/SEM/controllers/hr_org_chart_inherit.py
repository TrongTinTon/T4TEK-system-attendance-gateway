from odoo import http
from odoo.http import request
from odoo.addons.hr_org_chart.controllers.hr_org_chart import HrOrgChartController

class HrOrgChartInheritController(HrOrgChartController):

    @http.route('/hr/get_org_chart', type='jsonrpc', auth='user')
    def get_org_chart(self, employee_id, new_parent_id=None, **kw):
        # Móc (Hook) vào luồng get_org_chart để đánh cắp (intercept) version_id
        context = kw.get('context', {})
        version_id = context.get('version_id')

        # Dùng hàm gốc nếu không có yêu cầu coi version ở quá khứ
        if not version_id:
            return super().get_org_chart(employee_id, new_parent_id, **kw)

        # -----------------------------------------------------------
        # LUỒNG XỬ LÝ VERISON-CONTROLLED ORG CHART
        # -----------------------------------------------------------
        employee = self._get_employee(employee_id, **kw)
        if not employee:
            return {
                'managers': [],
                'children': [],
            }

        # Tìm version đang được focus
        v_id = version_id
        if v_id:
            if isinstance(v_id, (list, tuple)):
                v_id = v_id[0]
            elif isinstance(v_id, dict):
                v_id = v_id.get('id') or v_id.get('value')

        try:
            numeric_v_id = int(v_id)
        except (ValueError, TypeError):
            return super().get_org_chart(employee_id, new_parent_id, **kw)

        viewing_version = request.env['hr.version'].sudo().browse(numeric_v_id)
        if not viewing_version.exists():
            return super().get_org_chart(employee_id, new_parent_id, **kw)

        # Bóc tách Quản lý của phiên bản đó thay vì Quản lý hịện tại!
        # Phải cẩn thận phòng hờ trường hợp t4tek_hr_version không sync cột parent_id
        # Ta dùng hasattr để xem version có parent_id không.
        version_parent = False
        if hasattr(viewing_version, 'parent_id') and viewing_version.parent_id:
            version_parent = request.env['hr.employee.public'].sudo().browse(viewing_version.parent_id.id)
        
        # Nếu Version không có parent_id tĩnh, thử đọc từ Data Track JSON nếu có
        # Ở đây ta ưu tiên version_parent nếu được map qua hasattr
        current_parent_employee = version_parent if version_parent else False

        # Build cây Tổ chức ngược (Ancestors) tới Root
        ancestors = request.env['hr.employee.public'].sudo()
        current = employee.sudo()
        
        # Dùng current_parent_employee thay vì current.parent_id của hiện tại
        current_parent = current_parent_employee if current_parent_employee else current.parent_id

        max_level = (context.get('max_level') or self._managers_level) + 1
        
        while current_parent and current != current_parent and employee.sudo() != current_parent and len(ancestors) < max_level:
            # Nếu current_parent cũng có version tương ứng mốc thời gian đó, ta phải lấy cha của cái version đó!
            # Điều này giúp cây chạy mượt theo đúng sơ đồ "cả cty" ở thời điểm đó.
            current = current_parent
            
            # Quét version hợp lệ của current layer
            layer_version = request.env['hr.version'].sudo().search([
                ('employee_id', '=', current.id),
                ('is_approved', '=', True),
                ('date_version', '<=', viewing_version.date_version)
            ], order='date_version desc, id desc', limit=1)
            
            next_parent = False
            if layer_version and hasattr(layer_version[0], 'parent_id') and layer_version[0].parent_id:
                next_parent = request.env['hr.employee.public'].sudo().browse(layer_version[0].parent_id.id)
            else:
                next_parent = current.parent_id
            
            current_parent = next_parent

            if current_parent in ancestors:
                break
            ancestors += current

        # Con cái (children): Ta phải quét NHỮNG AI có parent_id là Employee này TẠI MỐC THỜI GIAN ĐÓ!
        # Chứ không phải con của thiện tại (employee.child_ids)
        # Truy vấn tất cả phiên bản hợp lệ của Cả công ty <= viewing_version.date_version để tìm con ruột
        all_latest_versions_at_that_time_query = """
            SELECT DISTINCT ON (employee_id) employee_id, parent_id
            FROM hr_version
            WHERE is_approved = true AND date_version <= %s
            ORDER BY employee_id, date_version DESC, id DESC
        """
        request.env.cr.execute(all_latest_versions_at_that_time_query, (viewing_version.date_version,))
        children_at_that_time = request.env.cr.dictfetchall()
        
        children_emp_ids = [row['employee_id'] for row in children_at_that_time if row['parent_id'] == employee.id]
        
        # Fallback lại native child_ids nếu version không track parent_id thành công
        if not children_at_that_time:
            children_emp_ids = employee.child_ids.ids

        children_records = request.env['hr.employee.public'].sudo().browse(children_emp_ids).filtered(lambda x: x != employee)

        values = dict(
            self=self._prepare_employee_data(employee),
            managers=[
                self._prepare_employee_data(ancestor)
                for idx, ancestor in enumerate(ancestors)
                if idx < max_level - 1
            ],
            managers_more=len(ancestors) > self._managers_level,
            children=[self._prepare_employee_data(child) for child in children_records],
        )
        values['managers'].reverse()
        return values
