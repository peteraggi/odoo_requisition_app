# -*- coding: utf-8 -*-
{
    'name': "requisitions",

    'summary': """
        Purchase, Stock and Cash Requisitions """,

    'description': """
        Purchase, Stock and Cash Requisitions 
    """,

    'author': "Scintl Tech",
    'website': "http://www.scintl.co.ug",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/14.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'account', 'purchase','stock','hr'],

    # always loaded
    'data': [
        'cash_requisition/security/security.xml',
        'cash_requisition/security/ir.model.access.csv',
        'cash_requisition/views/cash_requisition_view.xml',
        'cash_requisition/views/menus.xml',
        'item_requisition/security/security.xml',
        'item_requisition/security/ir.model.access.csv',
        'item_requisition/views/item_requisition_view.xml',
        'item_requisition/views/menus.xml',

        'views/menus.xml',
    ],
    'module_type': 'offical',
    'application': True,
}
