{
    'name': 'Realty - Master Data',
    'version': '19.0.0.1.1',
    'category': 'Realty',
    'summary': 'Common master data for the RealtyPro suite '
               '(bank registry, holidays, lookup tables).',
    'description': """
Master data shared across Realty Project, Sales, and Living.

This module intentionally starts as a thin shell. Existing master data
currently lives in domain-specific modules (banks in re_sale_program,
holidays likewise). When master data needs to be referenced from more
than one app, move the model here and have the app modules depend on
re_master_data.
    """,
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': [
        'base',
        're_base',
        'vn_administrative_units',
    ],
    'data': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
