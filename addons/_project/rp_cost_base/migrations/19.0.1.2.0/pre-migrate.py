# -*- coding: utf-8 -*-
"""Pre-migrate v1.4.3-r4: drop deprecated tables and clean common_cost.

Removed in r4:
1. Model rp.cost.plan + table rp_cost_plan
2. Model rp.cost.plan.line + table rp_cost_plan_line
3. Common Cost records on rp.structure (level=common_cost)
4. Field rp.structure.building_id

Strategy:
- DROP TABLE rp_cost_plan_line CASCADE (children first)
- DROP TABLE rp_cost_plan CASCADE
- DELETE FROM rp_structure WHERE structure_level = 'common_cost'
- ALTER TABLE rp_structure DROP COLUMN building_id (if exists)
- Clean ir_model_data references for these dropped models

The auto-Odoo-removal of an uninstalled model leaves orphaned
rows in ir_model_data; we clean them explicitly here.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        # Fresh install — no legacy artifacts to clean
        return

    _logger.info('rp_cost_base v1.4.3-r4 pre-migrate: cleanup from %s', version)

    # 1. DROP rp.cost.plan tables (child first due to FK)
    cr.execute("DROP TABLE IF EXISTS rp_cost_plan_line CASCADE")
    cr.execute("DROP TABLE IF EXISTS rp_cost_plan CASCADE")

    # 2. Remove ir_model_data for rp.cost.plan, rp.cost.plan.line
    cr.execute("""
        DELETE FROM ir_model_data
        WHERE module = 'rp_cost_base'
          AND model IN ('ir.model', 'ir.model.fields',
                        'ir.model.fields.selection',
                        'ir.actions.act_window', 'ir.ui.view',
                        'ir.ui.menu', 'ir.model.access')
          AND res_id IN (
              SELECT id FROM ir_model
              WHERE model IN ('rp.cost.plan', 'rp.cost.plan.line')
          )
    """)
    cr.execute("""
        DELETE FROM ir_model_fields
        WHERE model IN ('rp.cost.plan', 'rp.cost.plan.line')
    """)
    cr.execute("""
        DELETE FROM ir_model
        WHERE model IN ('rp.cost.plan', 'rp.cost.plan.line')
    """)

    # 3. Remove ir_model_data xmlids that reference dropped views/actions
    cr.execute("""
        DELETE FROM ir_model_data
        WHERE module = 'rp_cost_base'
          AND name IN (
              'action_rp_cost_plan_preliminary',
              'action_rp_cost_plan_detailed',
              'action_rp_cost_plan_budget',
              'view_rp_cost_plan_form',
              'view_rp_cost_plan_list',
              'view_rp_cost_plan_search',
              'view_rp_cost_plan_line_form',
              'view_rp_cost_plan_line_list'
          )
    """)

    # 4. Delete Common Cost records on rp.structure
    # First check if column exists in case fresh table
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'rp_structure' AND column_name = 'structure_level'
    """)
    if cr.fetchone():
        cr.execute("""
            DELETE FROM rp_structure
            WHERE structure_level = 'common_cost'
        """)
        deleted = cr.rowcount
        _logger.info('Deleted %d common_cost rp.structure records', deleted)

        # Also remove the orphan ir_model_data for is_common_cost selection
        cr.execute("""
            DELETE FROM ir_model_fields_selection
            WHERE field_id IN (
                SELECT id FROM ir_model_fields
                WHERE model = 'rp.structure' AND name = 'structure_level'
            )
            AND value = 'common_cost'
        """)

    # 5. Drop is_common_cost computed field column if it exists
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'rp_structure' AND column_name = 'is_common_cost'
    """)
    if cr.fetchone():
        cr.execute("ALTER TABLE rp_structure DROP COLUMN is_common_cost")
        _logger.info('Dropped rp_structure.is_common_cost column')

    # 6. Drop building_id column if exists
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'rp_structure' AND column_name = 'building_id'
    """)
    if cr.fetchone():
        cr.execute("ALTER TABLE rp_structure DROP COLUMN building_id")
        _logger.info('Dropped rp_structure.building_id column')

    _logger.info('rp_cost_base v1.4.3-r4 pre-migrate: done')
