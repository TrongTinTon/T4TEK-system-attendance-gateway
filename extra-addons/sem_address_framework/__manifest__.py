{
    'name': 'SEM Address Framework',
    'version': '19.0.1.0.0',
    "category": "SEMs",
    'summary': 'Standardized Address Mixin and OWL Widget',
    'description': """
        Provides an address.mixin and a generic OWL widget for consistent address rendering across Odoo.
    """,
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'data/res.country.state.csv',
        'data/res.state.ward.csv', 
        'views/res_state_ward_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sem_address_framework/static/src/components/address_widget/**/*',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
