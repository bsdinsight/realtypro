# -*- coding: utf-8 -*-
"""Lifecycle mixin for entities that own the project lifecycle state.

Vietnamese real-estate projects can be tracked at one of two granularities:

  - **Building** (per-tower): each tower in a high-rise development
    moves through the lifecycle independently. Tower S1 may be in
    `operation` while S2 is still `construction`.
  - **Subzone** (per-cluster): in a low-rise development (villas,
    townhouses, shophouses), it's the cluster ("Subzone The Origami")
    that moves through the lifecycle as a whole; individual buildings
    are mostly a logical grouping.

The choice is made on `re.project` via the ``lifecycle_level`` field.
Both `re.subzone` and `re.building` inherit this mixin and carry the
state field; whichever one matches the project's lifecycle_level is
the "owner" — the one whose buttons are visible and whose transitions
fire. The non-owner side displays a notice telling the user where to
manage state instead.

Project-level rollups (`re.project.primary_state`, `state_summary`)
are computed from whichever owners are active.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

LIFECYCLE_STATES = [
    ('planning',             'Planning'),
    ('pre_launch',           'Pre-Launch'),
    ('selling',              'Selling'),
    ('construction',         'Construction'),
    ('product_handover',     'Product Handover'),
    ('certificate_handover', 'Certificate Handover'),
    ('operation',            'Operation'),
    ('closed',               'Closed'),
]
"""The eight lifecycle phases for a Vietnamese real-estate project.

Order is the canonical order along the lifecycle; downstream code
uses this list (or :data:`STATE_ORDER`) to compare which state is
"farther along".

Note the explicit split between **product_handover** (key handover,
bàn giao nhà) and **certificate_handover** (sổ hồng / sổ đỏ
issuance). These two events are commonly months to years apart in
Vietnamese projects, with residents already living in the unit while
the certificate is still being processed.
"""

STATE_ORDER = [s[0] for s in LIFECYCLE_STATES]
"""Just the keys of LIFECYCLE_STATES, for ordinal comparison."""


# Filter presets used by each suite to default-show projects at the
# right lifecycle phase. Exported here so all four suites stay in
# sync if the state list ever changes.
SALES_LIFECYCLE_STATES = [
    'pre_launch', 'selling', 'construction',
    'product_handover', 'certificate_handover',
]
PROJECT_LIFECYCLE_STATES = [
    'planning', 'selling', 'construction', 'product_handover',
]
LIVING_LIFECYCLE_STATES = [
    'product_handover', 'certificate_handover', 'operation',
]


# ---------------------------------------------------------------------------
# Mixin
# ---------------------------------------------------------------------------

class RealtyLifecycleMixin(models.AbstractModel):
    """Inherited by re.subzone and re.building.

    Concrete classes must:
      - inherit ``mail.thread`` so ``tracking=True`` on ``state`` works
      - have a ``project_id`` Many2one to ``re.project``
      - implement :meth:`_expected_lifecycle_level` returning either
        ``'subzone'`` or ``'building'`` to identify which kind they are.

    Optionally override the action_* transition methods to add
    entity-specific validation (e.g. building requires units, subzone
    requires either buildings or units).
    """
    _name = 'realty.lifecycle.mixin'
    _description = 'Realty Project Lifecycle Mixin'

    state = fields.Selection(
        LIFECYCLE_STATES,
        default='planning',
        tracking=True,
        readonly=True,
        string='Phase',
        help="The current lifecycle phase. Read-only — change via the "
             "transition buttons on the form header.",
    )

    is_lifecycle_owner = fields.Boolean(
        compute='_compute_is_lifecycle_owner',
        store=True,
        help="True iff this record's level matches its project's "
             "lifecycle_level. Only owners show transition buttons; "
             "non-owners show a notice pointing to the right place.",
    )

    # ---- abstract ----------------------------------------------------------

    def _expected_lifecycle_level(self):
        """Return the lifecycle level this concrete model represents.

        Override in :class:`re.subzone` to return ``'subzone'`` and in
        :class:`re.building` to return ``'building'``.
        """
        raise NotImplementedError(
            "Subclasses of realty.lifecycle.mixin must override "
            "_expected_lifecycle_level()."
        )

    # ---- computes ----------------------------------------------------------

    @api.depends('project_id.lifecycle_level')
    def _compute_is_lifecycle_owner(self):
        for rec in self:
            project_level = rec.project_id.lifecycle_level
            rec.is_lifecycle_owner = (
                project_level == rec._expected_lifecycle_level()
            )

    # ---- guards ------------------------------------------------------------

    def _check_lifecycle_owner(self):
        """Raise if this record isn't its project's lifecycle owner.

        Used at the top of every transition button so users get a
        clear message if they somehow bypass the visibility rules.
        """
        for rec in self:
            if not rec.is_lifecycle_owner:
                project_level = rec.project_id.lifecycle_level or 'unset'
                raise UserError(_(
                    "Project %(project)s tracks its lifecycle at "
                    "%(level)s level, not at %(this_level)s level. "
                    "Use the buttons on the appropriate %(level)s "
                    "form instead.",
                    project=rec.project_id.display_name,
                    level=project_level,
                    this_level=rec._expected_lifecycle_level(),
                ))

    def _require_state(self, expected_states):
        """Raise unless the current state is in ``expected_states``.

        ``expected_states`` may be a single string or an iterable.
        """
        if isinstance(expected_states, str):
            expected_states = (expected_states,)
        for rec in self:
            if rec.state not in expected_states:
                raise UserError(_(
                    "%(name)s is in state '%(current)s'; this "
                    "transition requires one of: %(expected)s.",
                    name=rec.display_name,
                    current=rec.state,
                    expected=', '.join(expected_states),
                ))

    # ---- transitions -------------------------------------------------------
    #
    # Every transition follows the same shape:
    #   1. _check_lifecycle_owner — refuse if not the owner.
    #   2. _require_state(...) — refuse if currently in a wrong state.
    #   3. (optional, in subclasses) entity-specific validation.
    #   4. write the new state.
    #
    # Concrete models override transitions when extra validation is
    # warranted (e.g. building requires units, subzone requires
    # children, certificate handover requires all units to have
    # certificate_handover_date).

    def action_pre_launch(self):
        """Planning → Pre-Launch.

        Master data is complete enough to begin sales preparation
        (price lists, programs, marketing). No bookings allowed yet.
        """
        self._check_lifecycle_owner()
        self._require_state('planning')
        self.write({'state': 'pre_launch'})

    def action_open_for_sale(self):
        """Pre-Launch → Selling.

        Project is officially open for sale. From this point on,
        booking, deposit and contract operations become available
        in the Sales suite.
        """
        self._check_lifecycle_owner()
        self._require_state('pre_launch')
        self.write({'state': 'selling'})

    def action_start_construction(self):
        """Selling → Construction (optional metadata transition).

        Used when the project moves into the heavy-construction
        phase — most units are sold and focus shifts to building
        delivery. Sales may continue for residual units.
        """
        self._check_lifecycle_owner()
        self._require_state('selling')
        self.write({'state': 'construction'})

    def action_start_product_handover(self):
        """→ Product Handover. Bàn giao nhà — keys to residents.

        The Living suite begins operations from this point: residents
        move in, service fees, complaints, maintenance.
        """
        self._check_lifecycle_owner()
        self._require_state(('selling', 'construction'))
        self.write({'state': 'product_handover'})

    def action_start_certificate_handover(self):
        """→ Certificate Handover. Bàn giao sổ.

        Optional explicit phase. Some projects skip this and go
        straight to ``operation`` when product handover finishes,
        if certificates are issued in the same window. Most large
        projects, however, take 6 months to 2-3 years between
        product handover and certificate handover.
        """
        self._check_lifecycle_owner()
        self._require_state('product_handover')
        self.write({'state': 'certificate_handover'})

    def action_to_operation(self):
        """→ Operation. Sales/Project teams hand off entirely to Living.

        Subclasses may override to require all child units have a
        certificate_handover_date set.
        """
        self._check_lifecycle_owner()
        self._require_state(('product_handover', 'certificate_handover'))
        self.write({'state': 'operation'})

    def action_close(self):
        """→ Closed. Archive. Used decades into operation when the
        project is wound down or transferred."""
        self._check_lifecycle_owner()
        self.write({'state': 'closed', 'active': False})

    def action_reset_to_planning(self):
        """Emergency rollback — admin only.

        Deliberate friction (admin group + button class) so this
        isn't used casually. Useful when a record was advanced by
        mistake.
        """
        if not self.env.user.has_group('re_base.group_re_admin'):
            raise UserError(_(
                "Only Realty Admins may reset lifecycle state."
            ))
        self.write({'state': 'planning'})
