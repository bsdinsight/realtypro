# -*- coding: utf-8 -*-
"""Post-migrate v1.4.2: backfill existing projects with defaults.

Originally written for v1.4.2-r3 (which had Common Cost auto-create).
In v1.4.3-r4, Common Cost was removed. Since this hook may run
during a fresh install with rp_cost_base v1.4.3+ where the
helper method no longer exists, we guard with hasattr.

Idempotent: safe to call on already-seeded projects.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return  # Fresh install, no backfill needed

    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})

    Project = env['re.project']
    projects = Project.search([])

    _logger.info(
        'rp_cost_base v1.4.2 post-migrate: backfilling defaults for %d project(s)',
        len(projects)
    )

    Structure = env['rp.structure']
    has_common_cost_helper = hasattr(Structure, '_get_or_create_common_cost')

    for project in projects:
        env['rp.cost.category']._seed_defaults_for_project(project)
        # Common Cost helper was removed in v1.4.3-r4. Guard with hasattr
        # so this migration is forward-compatible.
        if has_common_cost_helper:
            Structure._get_or_create_common_cost(project)

    env.cr.commit()
    _logger.info('rp_cost_base v1.4.2 post-migrate: done')
