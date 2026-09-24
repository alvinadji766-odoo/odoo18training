{
    'name': 'Japfa - Sale Commision',
    'version': '18.0.1.0.0',
    'category': 'Uncategorized',
    'summary': '',
    'description': """
Long description of the module's purpose
========================================

""",
    'author': 'Japfa Odoo Dev',
    'website': 'https://odoo.com',
    'depends': ['base', 'sale', 'sale_management'],
    'data': [
        'security/ir.model.access.csv',
        'report/sale_report_templates.xml',
        'views/sale_order_views.xml',
        'views/menu.xml',
    ],
    'demo': [],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
