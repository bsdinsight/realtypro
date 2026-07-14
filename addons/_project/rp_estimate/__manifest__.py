# -*- coding: utf-8 -*-
{
    "name": "Realty Project - Estimate & Tender",
    "version": "19.0.1.9.0",
    "category": "Realty/Project",
    "summary": "Gói thầu (P5.1+P5.2+P5.3: KH lựa chọn NT + bidder "
               "+ tiêu chuẩn đánh giá + HSMT) + Khái toán",
    "description": """
Realty Project - Estimate & Tender (v1.4.3-r4)
===============================================

Phase 2 deliverable (v1.4.3-r4). Owns:

- ``rp.tender.package`` + ``rp.tender.package.line`` — Gói thầu
  basic. Phase 5 will _inherit to add awarding workflow.
- Realty Project root menu (xmlid `menu_realty_project_root`).
- Phase 2 submenus (Project Master + Estimate).
- Wizard: quick_create_structures (bulk create rp.structure).

**v1.4.3-r4 changes from r3**:
- Removed wizard ``create_detailed_from_preliminary`` — it referenced
  ``rp.cost.plan`` which was eliminated in r4. Phase 3 BOQ workflow
  will replace this with a new wizard.
- Menu "Khái toán" now points to ``action_rp_structure_estimate_summary``
  (pivot view of ``rp.structure.estimate.line``).
- Menus "Dự toán" and "Budget" removed — Phase 3 and Phase 4
  will add them back with new actions.
""",
    "author": "BSDInsight",
    "website": "https://bsdinsight.com",
    "license": "AGPL-3",
    "depends": [
        "rp_cost_base",
        "rp_contractor",
        "re_core",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/rp_tender_package_views.xml",
        "views/rp_tender_bidder_views.xml",
        "views/rp_tender_eval_criterion_views.xml",
        "wizards/quick_create_structures_views.xml",
        "views/menu_root.xml",
        "views/menus.xml",
    ],
    "application": True,
    "installable": True,
}
