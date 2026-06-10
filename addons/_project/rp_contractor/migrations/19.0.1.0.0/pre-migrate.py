# -*- coding: utf-8 -*-
"""Pre-migrate: drop iter5 placeholder rp.contractor stub.

The iter5 module had a minimal stub model:
  rp.contractor with: name, code, create_date, write_date (~5 fields)

v1.4.1 replaces it with a full model (3 field groups, ~25 fields,
state machine, specialty M2M). Schema is incompatible.

Strategy: DROP TABLE + DELETE ir_model_data, let fresh install
recreate. Acceptable because iter5 placeholder had no real production
data (dev DB has at most a few test rows).

Also moves the module location reference in ir_module_module — Odoo
typically handles this automatically when the manifest's location
changes; this script is a safety net.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return  # Fresh install, no iter5 artifacts

    _logger.info(
        'rp_contractor v1.4.1 pre-migrate: dropping iter5 stub from version %s',
        version
    )

    # 1. Drop the iter5 stub table (cascade FKs)
    cr.execute("DROP TABLE IF EXISTS rp_contractor CASCADE")

    # 2. Remove ir_model rows for the stub model
    cr.execute("DELETE FROM ir_model WHERE model = 'rp.contractor'")
    cr.execute("DELETE FROM ir_model_fields WHERE model = 'rp.contractor'")

    # 3. Remove ir_model_data for menus, views, actions owned by iter5
    cr.execute("""
        DELETE FROM ir_model_data
        WHERE module = 'rp_contractor'
          AND model IN ('rp.contractor', 'ir.ui.menu',
                        'ir.actions.act_window', 'ir.ui.view',
                        'ir.model.access')
    """)

    # 4. Clean up orphan access ACLs that pointed at the stub model
    cr.execute("""
        DELETE FROM ir_model_access
        WHERE model_id IN (
            SELECT id FROM ir_model WHERE model = 'rp.contractor'
        )
    """)

    _logger.info('rp_contractor v1.4.1 pre-migrate: done')
