from odoo import fields, models


class HrEmployeePublicInherit(models.Model):
    _inherit = 'hr.employee.public'

    manager_id = fields.Many2one('hr.employee', string='Quản lý phòng ban', readonly=True)
    place_of_origin = fields.Char(string='Quê quán', readonly=True)
    people_id = fields.Many2one('people.category', string='Dân tộc', readonly=True)
    religion_id = fields.Many2one('religion.category', string='Tôn giáo', readonly=True)

    private_street = fields.Char(string='Số/Ngõ (Thường trú)', readonly=True)
    private_street2 = fields.Char(string='Đường (Thường trú)', readonly=True)
    private_city = fields.Char(string='Thành phố (Thường trú)', readonly=True)
    private_state_id = fields.Many2one('res.country.state', string='Tỉnh/Thành (Thường trú)', readonly=True)
    private_zip = fields.Char(string='Mã bưu chính (Thường trú)', readonly=True)
    private_state_ward = fields.Many2one('res.state.ward', string='Phường Xã (Thường trú)', readonly=True)

    temp_street = fields.Char(string='Tạm trú - Số nhà', readonly=True)
    temp_street2 = fields.Char(string='Tạm trú - Đường 2', readonly=True)
    temp_city = fields.Char(string='Tạm trú - Thành phố', readonly=True)
    temp_state_ward = fields.Many2one('res.state.ward', string='Phường Xã', readonly=True)
    temp_state_id = fields.Many2one('res.country.state', string='Tạm trú - Tỉnh/Thành', readonly=True)
    temp_zip = fields.Char(string='Tạm trú - Mã bưu chính', readonly=True)

    permanent_address = fields.Char(string='Địa chỉ thường chú', readonly=True)
    temporary_address = fields.Char(string='Địa chỉ tạm trú', readonly=True)

    salary_type = fields.Selection([
        ('Monthly', 'Lương theo tháng'),
        ('Daily', 'Lương theo ngày'),
        ('Hourly', 'Lương theo giờ'),
    ], string='Loại lương', readonly=True)

    private_country_id = fields.Many2one('res.country', readonly=True)
    temp_country_id = fields.Many2one('res.country', string='Tạm trú - Quốc gia', readonly=True)

    probation_date = fields.Date(string='Ngày thử việc', readonly=True)
    probation_period = fields.Integer(string='Thời gian thử việc (Ngày)', readonly=True)

    start_date = fields.Date(string='Ngày chính thức', readonly=True)
    end_date = fields.Date(string='Ngày nghỉ việc', readonly=True)

    cultural_level_id = fields.Many2one('cultural.level.category', string='Trình độ văn hóa', readonly=True)
    date_issuance_identity_card = fields.Date(string='Ngày cấp CCCD', readonly=True)
    local_issuance_identity_card = fields.Char(string='Nơi cấp CCCD', readonly=True)

    code = fields.Char(string='Mã nhân viên', readonly=True)
    id_number = fields.Char(string='Số ID', readonly=True)

    @api.model
    def _get_fields(self):
        res_fields = super()._get_fields()
        # Fix Bootstrap SQL error: hr_version.parent_id is not physically created yet during HR public view init
        if 'v.parent_id' in res_fields:
            res_fields = res_fields.replace('v.parent_id', 'e.parent_id')
        return res_fields