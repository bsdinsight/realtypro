# -*- coding: utf-8 -*-
"""Realty Core — UI shell module.

Most of the work in this module is declarative XML (categories,
menus). The Python side is just a post-install hook that fixes up
``ir.module.category`` records when re_core lands in a database that
already has Realty modules installed under auto-created categories.
"""
import logging

_logger = logging.getLogger(__name__)


def _post_init_link_categories(env):
    """Consolidate Realty module categories onto the XML-tracked records.

    When a customer DB has Realty modules installed *before* re_core
    (because re_core wasn't part of an earlier release, or the module
    install order put re_party / vn_administrative_units first),
    Odoo creates an ``ir.module.category`` named "Realty" on the fly
    with no XML ID. When re_core then loads its ``data/categories.xml``,
    Odoo creates a *second* "Realty" record bound to the XML ID
    ``re_core.module_category_realty``. Result: two categories with
    the same display name in the Apps sidebar.

    This hook detects orphan ("Realty", "Sales", "Project", "Living")
    categories — same name, no `module.` XML ID, possibly empty —
    repoints any modules attached to them onto the canonical
    XML-tracked record, then deletes the orphans.
    """
    # Map of (canonical_xml_id, expected_parent_xml_id_or_None,
    #         category_name) to apply. Order matters: parent first,
    # otherwise re-parenting a child to a parent that hasn't been
    # consolidated yet leaves intermediate state.
    canonical_specs = [
        ('re_core.module_category_realty',         None,
         'Realty'),
        ('re_core.module_category_realty_sales',   'Realty',
         'Sales'),
        ('re_core.module_category_realty_project', 'Realty',
         'Project'),
        ('re_core.module_category_realty_living',  'Realty',
         'Living'),
    ]

    Category = env['ir.module.category']
    Module = env['ir.module.module']

    for xmlid, parent_name, cat_name in canonical_specs:
        canonical = env.ref(xmlid, raise_if_not_found=False)
        if not canonical:
            # Shouldn't happen — categories.xml just loaded — but be
            # defensive in case an admin deleted it.
            _logger.warning("re_core: canonical category %s missing", xmlid)
            continue

        # Find orphans: same display name, different id, and not the
        # canonical one. For sub-categories, additionally require the
        # parent to be the canonical Realty (so we don't sweep up
        # unrelated "Sales" categories from Odoo core).
        domain = [
            ('id', '!=', canonical.id),
            ('name', '=', cat_name),
        ]
        if parent_name == 'Realty':
            realty = env.ref(
                're_core.module_category_realty', raise_if_not_found=False,
            )
            if realty:
                # Match orphan whose parent has the same name as ours.
                domain.append(('parent_id.name', '=', 'Realty'))

        orphans = Category.search(domain)
        if not orphans:
            continue

        # Re-point any modules off the orphans onto the canonical.
        attached = Module.search([('category_id', 'in', orphans.ids)])
        if attached:
            attached.write({'category_id': canonical.id})
            _logger.info(
                "re_core: moved %d module(s) from orphan %r to %s",
                len(attached), cat_name, xmlid,
            )

        # Re-parent any child categories of orphans onto the canonical
        # before deletion so we don't dangle the children.
        children = Category.search([('parent_id', 'in', orphans.ids)])
        if children:
            children.write({'parent_id': canonical.id})

        # Now safe to drop the orphans.
        orphans.unlink()
        _logger.info(
            "re_core: removed %d orphan %r category record(s)",
            len(orphans), cat_name,
        )
