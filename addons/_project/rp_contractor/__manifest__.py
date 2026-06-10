# -*- coding: utf-8 -*-
{
    "name": "Realty Project - Contractors",
    "version": "19.0.2.0.0",
    "category": "Realty/Project",
    "summary": "Nhà thầu (contractor) master data + specialty registry",
    "description": """
Realty Project - Contractors (v1.4.1)
=====================================

**TRANSFORMED in v1.4.1** from iter5 placeholder stub.

Owns:

- ``rp.contractor`` — Nhà thầu master data with three field groups:
  - Identity & Vietnam legal (name, code, tax_code, business_license)
  - Construction capability (construction_license, class, expiry,
    specialty, contractor_type)
  - Project relationship & lifecycle (project_ids, contacts, state)
- ``rp.contractor.specialty`` — Helper master with seeded Vietnamese
  defaults (Móng cọc, Kết cấu, MEP, Facade, PCCC, ...)

Phase 2 v1.4.1 ships the basic model. Phase 5 will inherit to add:
- Performance KPI fields
- Insurance certificate tracking
- Awarding workflow integration with rp.tender.package

Module location: ``addons/_common/rp_contractor/``
Rationale: contractor master may be shared with Realty CRM (HĐMB
nhà thầu, future) and Realty Living (maintenance contractors).
The ``rp_*`` prefix is retained (NOT renamed to ``re_contractor``)
to minimize rename pain; see v1.4.1 design Section 2.4 for the
namespace exception note.

Menu placement: NONE. Actions are declared; menus are mounted by
``rp_estimate`` (suite root owner) under Project Master submenu.

Migration (v1.4.1):
- Pre-migrate drops the iter5 placeholder ``rp.contractor`` stub
  (table ``rp_contractor`` with demo fields) before fresh install
  creates the real schema.
""",
    "author": "BSDInsight",
    "website": "https://bsdinsight.com",
    "license": "AGPL-3",
    "depends": [
        "re_base",
        "mail",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/rp_contractor_specialty_data.xml",
        "views/rp_contractor_specialty_views.xml",
        "views/rp_contractor_views.xml",
    ],
    "application": False,
    "installable": True,
}
