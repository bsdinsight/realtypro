# -*- coding: utf-8 -*-
"""Pre-migrate for re_pricing_base v1.1 → v1.4 (19.0.2.0.0).

In v1.1, re_pricing_base owned:
- re.structure (model + table re_structure)
- rp.cost.category (model + table rp_cost_category)
- Menus: re_pricing_base.menu_realty_project_root, etc.
- ir.actions.act_window records
- ir.model.access ACLs

In v1.4, ALL of these move out:
- re.structure → rp_estimate (renamed to rp.structure, table rp_structure)
- rp.cost.category, rp.cost.plan, rp.cost.plan.line → rp_cost_base
- Menus → rp_estimate
- Actions → rp_cost_base + rp_estimate

This pre-migrate runs the destructive cleanup (Mode 1) for dev DB.
After cleanup:
- rp_cost_base install creates fresh rp_cost_category / rp_cost_plan
  / rp_cost_plan_line tables.
- rp_estimate install creates fresh rp_structure table.
- rp_estimate's post-migrate backfills existing projects with the
  default cost categories + Common Cost structure.

NOTE: this script is intentionally destructive. v1.1 test data on
the dev DB is acceptable to lose. For a production deployment, a
Mode 2 (preserve-data) migration would be needed instead — written
when a production customer exists.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        # Fresh install — no v1.1 artifacts to clean
        return

    _logger.info(
        're_pricing_base v1.4 pre-migrate: dropping v1.1 artifacts '
        '(from version %s)',
        version
    )

    # 1. Drop v1.1 tables (cascade FKs)
    cr.execute("DROP TABLE IF EXISTS rp_cost_plan_line CASCADE")
    cr.execute("DROP TABLE IF EXISTS rp_cost_plan CASCADE")
    cr.execute("DROP TABLE IF EXISTS rp_cost_category CASCADE")
    cr.execute("DROP TABLE IF EXISTS re_structure CASCADE")

    # 2. Drop ir_model rows for v1.1 models
    cr.execute("""
        DELETE FROM ir_model
        WHERE model IN (
            'rp.cost.category', 'rp.cost.plan', 'rp.cost.plan.line',
            're.structure'
        )
    """)
    cr.execute("""
        DELETE FROM ir_model_fields
        WHERE model IN (
            'rp.cost.category', 'rp.cost.plan', 'rp.cost.plan.line',
            're.structure'
        )
    """)

    # 3. Drop ALL ir_model_data rows owned by re_pricing_base
    cr.execute("""
        DELETE FROM ir_model_data
        WHERE module = 're_pricing_base'
    """)

    # 4. Drop access ACLs that pointed at v1.1 models (defensive;
    #    ir_model rows are already gone above so this is a no-op,
    #    but kept for clarity)
    cr.execute("""
        DELETE FROM ir_model_access
        WHERE model_id NOT IN (SELECT id FROM ir_model)
    """)

    # 5. Drop v1.1 menu records that pointed at re_pricing_base.menu_xxx
    #    (already cleared by step 3, but defensive cleanup of orphans)
    cr.execute("""
        DELETE FROM ir_ui_menu
        WHERE name IN (
            'Realty Project',  -- v1.1 had root here; v1.4 moved to rp_estimate
            'Project Master',
            'Cost Categories'
        )
          AND id NOT IN (SELECT res_id FROM ir_model_data WHERE model = 'ir.ui.menu')
    """)

    _logger.info('re_pricing_base v1.4 pre-migrate: done')
