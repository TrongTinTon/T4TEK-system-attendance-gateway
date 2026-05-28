# -*- coding: utf-8 -*-
from odoo import api, models
import logging

_logger = logging.getLogger(__name__)


class HrEmployeeInherit(models.Model):
    _inherit = 'hr.employee'

    @api.model
    def _name_search(self, name='', domain=None, operator='ilike', limit=None, order=None):
        """
        Mở rộng tìm kiếm nhân viên để hỗ trợ tìm theo barcode.
        Khi import chấm công từ Excel, Odoo sẽ dùng _name_search để match
        giá trị cột "Nhân viên" với record hr.employee.
        Override này cho phép match bằng barcode thay vì chỉ bằng tên.
        """
        domain = domain or []

        if name and operator in ('=', 'ilike', 'like', '=ilike', '=like'):
            # Tìm theo mã nhân viên (code) - exact match trước
            code_domain = domain + [('code', '=', name)]
            employee_ids = self._search(code_domain, limit=limit, order=order)
            if employee_ids:
                return employee_ids

            # Tìm theo mã nhân viên (code) - partial match
            if operator in ('ilike', 'like'):
                code_partial_domain = domain + [('code', operator, name)]
                employee_ids = self._search(code_partial_domain, limit=limit, order=order)
                if employee_ids:
                    return employee_ids

            # Tìm theo barcode (exact match)
            barcode_domain = domain + [('barcode', '=', name)]
            employee_ids = self._search(barcode_domain, limit=limit, order=order)
            if employee_ids:
                return employee_ids

            # Tìm theo barcode (partial match)
            if operator in ('ilike', 'like'):
                barcode_partial_domain = domain + [('barcode', operator, name)]
                employee_ids = self._search(barcode_partial_domain, limit=limit, order=order)
                if employee_ids:
                    return employee_ids

        # Fallback về tìm kiếm mặc định (theo tên)
        return super()._name_search(name=name, domain=domain, operator=operator, limit=limit, order=order)
