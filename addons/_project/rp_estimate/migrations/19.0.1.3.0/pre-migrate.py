# -*- coding: utf-8 -*-
"""Pre-migrate rp_estimate v1.4.3-r4.

Cleanup obsolete xmlids and DB records for:
1. Wizard ``rp.wizard.create.detailed.from.preliminary`` — removed in r4
   because it referenced rp.cost.plan (also removed).
2. Menus ``menu_estimate_detailed`` and ``menu_estimate_budget`` — removed
   in r4. Phase 3 (BOQ → Dự toán) and Phase 4 (Budget) will re-add them.

After Odoo loads the new module manifest (without these xmlids), it
would not know to clean them. So we explicitly drop:
- ir.ui.menu records for the obsolete menus + their ir_model_data
- ir.actions.act_window for the wizard
- TransientModel rp_wizard_create_detailed_from_preliminary table
  (if persisted somehow — TransientModel rows are auto-cleaned but
  the model registration might linger)
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return  # Fresh install — nothing to clean

    _logger.info('rp_estimate v1.4.3-r4 pre-migrate: cleanup from %s', version)

    # 1. Delete obsolete menu xmlids + records
    # menu_estimate_detailed, menu_estimate_budget
    cr.execute("""
        SELECT res_id FROM ir_model_data
        WHERE module = 'rp_estimate'
          AND model = 'ir.ui.menu'
          AND name IN ('menu_estimate_detailed', 'menu_estimate_budget')
    """)
    menu_ids = [row[0] for row in cr.fetchall()]
    if menu_ids:
        cr.execute(
            "DELETE FROM ir_ui_menu WHERE id = ANY(%s)",
            (menu_ids,)
        )
        _logger.info('Deleted %d obsolete Estimate menus', len(menu_ids))

    cr.execute("""
        DELETE FROM ir_model_data
        WHERE module = 'rp_estimate'
          AND model = 'ir.ui.menu'
          AND name IN ('menu_estimate_detailed', 'menu_estimate_budget')
    """)

    # 2. Drop wizard transient model artifacts
    cr.execute("DROP TABLE IF EXISTS rp_wizard_create_detailed_from_preliminary CASCADE")

    cr.execute("""
        DELETE FROM ir_model_fields
        WHERE model = 'rp.wizard.create.detailed.from.preliminary'
    """)
    cr.execute("""
        DELETE FROM ir_model
        WHERE model = 'rp.wizard.create.detailed.from.preliminary'
    """)

    # 3. Cleanup the wizard's xmlids in ir_model_data
    cr.execute("""
        DELETE FROM ir_model_data
        WHERE module = 'rp_estimate'
          AND (name LIKE 'view_rp_wizard_create_detailed%'
               OR name LIKE 'action_rp_wizard_create_detailed%'
               OR name = 'access_rp_wiz_detailed_manager')
    """)

    _logger.info('rp_estimate v1.4.3-r4 pre-migrate: done')
