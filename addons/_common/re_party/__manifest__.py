{
    'name': 'Realty - Party',
    'version': '19.0.0.5.0',
    'category': 'Realty',
    'summary': 'Vietnam-specific identity fields on res.partner '
               '(tax code, national ID, household registration) shared '
               'across the RealtyPro suite.',
    'description': """
Inherit res.partner with the identity fields commonly required by
Vietnamese real-estate workflows:

* National ID (CMND/CCCD) + issue date + issue place
* Passport number for foreigners
* Tax code (mã số thuế) for legal entities
* Secondary phone
* RealtyPro role tag (customer / vendor / contractor / resident /
  broker / distributor) — non-exclusive, multiple flags allowed
* Permanent address (Nơi thường trú) for HĐMB legal documents
* Family / personal relationships (vợ/chồng, cha, mẹ, con, …) declared
  inline on the partner form — required by Vietnamese HĐMB workflow

Across the three sub-suites (Project, Sales, Living) a single legal
person can play several roles. The role tags are flags rather than a
selection so a customer who later becomes a resident keeps both flags.
    """,
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': ['base', 'contacts', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_partner_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
