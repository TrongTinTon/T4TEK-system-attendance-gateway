import re
import logging
from odoo import api, fields, models, tools
from odoo.osv import expression
from odoo.exceptions import UserError
from psycopg2 import IntegrityError
from odoo.tools.translate import _
_logger = logging.getLogger(__name__)

class ResWardState(models.Model):
    _name = 'res.state.ward' 
    _order = 'code'
    _rec_names_search = ['name', 'code']


    code = fields.Char(string='Ward Code', help='The ward code.', required=True)
    _sql_constraints = [
        ('name_code_uniq', 'unique(ward_id, code)', 'The code of the state must be unique by country!')
    ]


    country_state_id = fields.Many2one('res.country.state', string='Country State')
    name = fields.Char(string='Ward Name', required=True,
               help='Cập nhật phường xã')



    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100, **kwargs):
        result = []
        domain = kwargs.get('domain', args) or []
        # first search by code (with =ilike)
        if operator not in expression.NEGATIVE_TERM_OPERATORS and name:
            states = self.search_fetch(expression.AND([domain, [('code', '=like', name)]]), ['display_name'], limit=limit)
            result.extend((state.id, state.display_name) for state in states.sudo())
            domain = expression.AND([domain, [('id', 'not in', states.ids)]])
            if limit is not None:
                limit -= len(states)
                if limit <= 0:
                    return result
        # normal search
        if 'domain' in kwargs:
            kwargs['domain'] = domain
            result.extend(super().name_search(name, operator=operator, limit=limit, **kwargs))
        else:
            result.extend(super().name_search(name, domain, operator, limit, **kwargs))
        return result

    @api.model
    def _search_display_name(self, operator, value):
        domain = super()._search_display_name(operator, value)
        if value and operator not in expression.NEGATIVE_TERM_OPERATORS:
            if operator in ('ilike', '='):
                domain = expression.OR([
                    domain, self._get_name_search_domain(value, operator),
                ])
            elif operator == 'in':
                domain = expression.OR([
                    domain,
                    *(self._get_name_search_domain(name, '=') for name in value),
                ])
        if country_state_id := self.env.context.get('country_state_id'):
            domain = expression.AND([domain, [('country_state_id', '=', country_state_id)]])
        return domain

    def _get_name_search_domain(self, name, operator):
        m = re.fullmatch(r"(?P<name>.+)\((?P<country>.+)\)", name)
        if m:
            return [
                ('name', operator, m['name'].strip()),
                '|', ('country_state_id.name', 'ilike', m['country'].strip()),
                ('country_state_id.code', '=', m['country'].strip()),
            ]
        return [expression.FALSE_LEAF]

    @api.depends('country_state_id')
    def _compute_display_name(self):
        for record in self:
            record.display_name = record.name
