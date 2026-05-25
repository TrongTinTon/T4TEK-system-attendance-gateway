from odoo import models, fields, api

class AddressMixin(models.AbstractModel):
    _name = 'address.mixin'
    _description = 'Standard Address Mixin'

    street = fields.Char(string='số nhà', help="địa chỉ cấp 1: số nhà (người dùng nhập tùy ý)")
    street2 = fields.Char(string='khu vực', help="địa chỉ cấp 2: khu vực, khu dân cư, đường phố (người dùng nhập tùy ý)")
    city_id = fields.Many2one('res.state.ward', string='Phường Xã', help="Phường / Xã / Thành phố (cấp tỉnh)")
    state_id = fields.Many2one('res.country.state', string='Tỉnh/Thành', domain="[('country_id', '=?', country_id)]", 
                                help="Tỉnh / Thành (cấp trung ương - thành phố cấp 1)")
    country_id = fields.Many2one('res.country', string='Quốc gia', ondelete='restrict')
    zip = fields.Char(string='Zip/Postal Code', change_default=True)

    full_address = fields.Char(
        string='Full Address',
        compute='_compute_full_address',
        store=True,
    )

    @api.depends('street', 'street2', 'city_id', 'state_id', 'zip', 'country_id')
    def _compute_full_address(self):
        for record in self:
            parts = [
                record.street,
                record.street2,
                record.city_id.name if record.city_id else False,
                record.state_id.name if record.state_id else False,
                record.zip,
                record.country_id.name if record.country_id else False,
            ]
            record.full_address = ', '.join(filter(bool, parts))


class SemAddressBaseExtend(models.AbstractModel):
    _inherit = 'base'

    @api.model
    def get_views(self, views, options=None):
        res = super().get_views(views, options)
        if 'views' in res and 'form' in res['views']:
            arch_str = res['views']['form'].get('arch')
            if arch_str and 'widget="sem_address"' in arch_str:
                from lxml import etree
                import ast
                try:
                    arch = etree.fromstring(arch_str.encode('utf-8'))
                    modified = False
                    for node in arch.xpath('//field[@widget="sem_address"]'):
                        opts_str = node.get('options')
                        if opts_str:
                            try:
                                opts = ast.literal_eval(opts_str)
                                fields_to_add = [
                                    opts.get('street'), opts.get('street2'),
                                    opts.get('city'), opts.get('state_id'),
                                    opts.get('country_id'), opts.get('zip')
                                ]
                                for f_name in fields_to_add:
                                    if f_name and not arch.xpath(f'//field[@name="{f_name}"]'):
                                        attrs = {'name': f_name, 'invisible': '1'}
                                        # Auto-inject standard cascading domains
                                        if f_name == opts.get('state_id') and opts.get('country_id'):
                                            attrs['domain'] = f"[('country_id', '=?', {opts.get('country_id')})]"
                                        if f_name == opts.get('city') and opts.get('state_id'):
                                            attrs['domain'] = f"[('country_state_id', '=?', {opts.get('state_id')})]"
                                        
                                        inv_node = etree.Element('field', attrs)
                                        node.addnext(inv_node)
                                        modified = True
                            except Exception:
                                pass
                    if modified:
                        res['views']['form']['arch'] = etree.tostring(arch, encoding='unicode')
                except Exception as e:
                    pass
        return res

   