# -*- coding: utf-8 -*-
{
    "name": "Realty - Vendors",
    "version": "19.0.0.1.1",
    "category": "Realty",
    "summary": "🚧 Đang phát triển - Shared vendor / contractor registry",
    "description": """
Realty - Vendor
===============

Single source of truth for all vendors and contractors a real-estate operator works with. The same vendor record can act as construction contractor (Project), service provider (Living maintenance), broker partner (Sales distribution), or supplier of any kind. Sub-suites extend the base model with role-specific fields: rp_contractor adds construction license + KPI, rl_maintenance adds SLA + service categories, rs_distributor_portal adds commission tier.

**Status: Placeholder / Work In Progress.**

Planned models:
  - re.vendor
  - re.vendor.category
  - re.vendor.evaluation

This module ships as a skeleton so other modules can declare it as a
dependency today and start using its (eventual) APIs. Until the
implementation lands, installing this module only adds the manifest
record; no models or menus are created.
""",
    "author": "BSDInsight",
    "website": "https://bsdinsight.com",
    "license": "AGPL-3",
    "depends": ['re_base', 're_party', 'mail'],
    "data": [
        "security/ir.model.access.csv",
    ],
    "application": False,
    "installable": True,
}
