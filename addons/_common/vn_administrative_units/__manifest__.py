{
    'name': 'Realty - VN Administrative Units',
    'version': '19.0.3.3.0',
    'category': 'Realty',
    'summary': 'Vietnam administrative units (34 provinces + 3,321 wards) per Decree 19/2025/QĐ-TTg',
    'description': """
Vietnam Administrative Units (Đơn vị hành chính Việt Nam)
==========================================================

After the 2025 administrative reform (effective 1/7/2025), Vietnam has:
* **34 provinces / cities** (28 tỉnh + 6 thành phố trực thuộc TW)
* **3,321 wards / communes** (phường, xã, đặc khu)
* District level abolished — only 2 levels: Province → Ward

Reference: Resolution 202/2025/QH15, Decree 19/2025/QĐ-TTg.

What this module does
---------------------
* Seeds 34 Vietnamese provinces into ``res.country.state`` (Odoo standard)
* Creates new model ``vau.ward`` with all 3,321 wards/communes
* Extends ``res.partner`` with ward_id field
* Overrides address layout to Vietnamese convention:
    - Street (số nhà + tên đường)
    - Phường/Xã (dropdown, cascaded from province)
    - Tỉnh/Thành (dropdown, filtered to Vietnam)
    - Quốc gia (default = Vietnam)
* Sets default country to Vietnam for new partners

Data source
-----------
Province and ward names follow Decree 19/2025/QĐ-TTg.
Codes follow GSO (General Statistics Office) numbering.
    """,
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': [
        'base',
        'contacts',
        'crm',
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',

        # Data: 34 provinces (loaded into res.country.state)
        'data/res_country_state_data.xml',

        # Data: 3,321 wards (separate model)
        'data/vau_ward_data.xml',

        # Views
        'views/vau_ward_views.xml',
        'views/res_partner_views.xml',
        'views/res_bank_views.xml',
        'views/crm_lead_views.xml',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
}
