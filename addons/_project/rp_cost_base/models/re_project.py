# -*- coding: utf-8 -*-
"""re.project inherit — auto-seed default cost categories per project.

v1.4.3-r4: simplified — only seeds 83 default cost categories.
Common Cost auto-create logic was removed in r4 because the
``common_cost`` structure level was eliminated; common-pool costs
are now modeled as regular cost categories on whichever structure
is appropriate.

The seed hook is idempotent: re-running on a project that already
has cost categories is a no-op.
"""

from odoo import api, models


class ReProject(models.Model):
    _inherit = 're.project'

    @api.model_create_multi
    def create(self, vals_list):
        projects = super().create(vals_list)
        for project in projects:
            self.env['rp.cost.category']._seed_defaults_for_project(project)
        return projects
