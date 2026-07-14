# -*- coding: utf-8 -*-
{
    "name": "Realty Project - Cost Base",
    "version": "19.0.1.2.0",
    "category": "Realty/Project",
    "summary": "Cost-management foundation: structures, categories, Khái toán inline",
    "description": """
Realty Project - Cost Base (v1.4.3-r4)
======================================

Foundation models for cost management in Realty Project suite.

Models in this module:

- ``rp.structure`` — Hạng mục dự án / Sub-hạng mục.
  Two-level hierarchy (item → sub_item). The Common Cost level
  was removed in v1.4.3-r4; common-pool costs are now modeled as
  regular cost categories on whichever structure is appropriate.
  Building field also removed in r4 (use re.building separately).
- ``rp.cost.category`` — Project-scoped 3-level cost classification
  tree (Nhóm chi phí). Auto-seeded with a Vietnamese real-estate
  default set (11 L1 + 72 L2 = 83 records) when a project is created.
- ``rp.structure.estimate.line`` — Khái toán line. **NEW in r4**.
  Each line: structure × category × amount. Entered inline on the
  structure form (Khái toán tab). Aggregation view at Estimate menu
  shows pivot rows=structure × cols=category × cells=amount.

**Removed in r4**:
- ``rp.cost.plan`` and ``rp.cost.plan.line`` — replaced by the
  simpler ``rp.structure.estimate.line`` inline pattern. Phase 4
  Budget will be redesigned from scratch.
- ``rp.structure._get_or_create_common_cost`` — common-pool costs
  now use regular categories on regular structures.
- ``rp.structure.building_id`` — not used in Phase 2; Phase 3+ can
  _inherit and add back if needed.

Menu placement: NONE for the model actions themselves. Menus that
mount the actions live in ``rp_estimate``:
- Project Master → Hạng mục dự án (action_rp_structure)
- Project Master → Cost Categories (action_rp_cost_category)
- Estimate → Khái toán (action_rp_structure_estimate_summary)
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
        "views/rp_structure_views.xml",
        "views/rp_cost_category_views.xml",
        "views/rp_cost_category_master_views.xml",
        "views/rp_structure_estimate_line_views.xml",
    ],
    "application": False,
    "installable": True,
}
