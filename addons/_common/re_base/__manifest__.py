{
    'name': 'Realty - Base',
    'version': '19.0.5.4.0',
    'category': 'Realty',
    'summary': 'Master data: Project, Subzone, Building, Floor, Unit Type, Unit',
    'description': """
Real Estate Base Module - Master data only
==========================================

Comprehensive master data for Vietnamese real estate:

* **Project** - root entity with full marketing, legal, contact info
* **Subzone** - optional zones within mega projects (Vịnh Ngọc, Đảo Mặt Trời...)
* **Building** - buildings/blocks with construction progress
* **Floor** - floors with auto-generation wizard
* **Unit Type** - 12 categories with seeded sample data (STUDIO, 1BR, ..., VILLA)
* **Unit** - sellable unit with full pricing/legal/handover info

The 8-phase project lifecycle (planning → pre_launch → selling →
construction → product_handover → certificate_handover → operation
→ closed) lives in the ``realty.lifecycle.mixin`` and is shared by
``re.subzone`` and ``re.building``.

NOTE: This module is a *technical foundation* (application=False).
The user-facing top menu lives in ``re_core``, which assembles the
master-data screens defined here under a "Realty Core" suite. Do
not install ``re_base`` alone for end users — install ``re_core``.

Vietnam-specific:
- Date format: DD/MM/YYYY (real estate transactions span years).
  Applied via JS patch on DateTimeField default props.
- Address: 34 provinces + 3,321 wards/communes seeded via
  ``vn_administrative_units`` dependency. Default country = Vietnam.
    """,
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': [
        'base',
        'mail',
        'web',
        'vn_administrative_units',
    ],
    'data': [
        # Security first
        'security/re_base_security.xml',
        'security/ir.model.access.csv',

        # Sequences
        'data/ir_sequence_data.xml',

        # Language date format (DD/MM/YYYY for real estate)
        'data/res_lang_data.xml',

        # Seed data
        'data/re_unit_type_data.xml',

        # Wizards FIRST (actions referenced by view buttons)
        'wizards/re_floor_generate_wizard_views.xml',
        'wizards/re_floor_import_wizard_views.xml',
        'wizards/re_unit_import_wizard_views.xml',

        # Views (define act_window actions but no menus —
        # menus are mounted by re_core)
        'views/re_project_views.xml',
        'views/re_subzone_views.xml',
        'views/re_building_views.xml',
        'views/re_floor_views.xml',
        'views/re_unit_type_views.xml',
        'views/re_unit_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            're_base/static/src/js/date_format_override.js',
        ],
    },
    'application': False,
    'installable': True,
}
