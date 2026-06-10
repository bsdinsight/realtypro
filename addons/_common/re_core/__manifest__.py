# -*- coding: utf-8 -*-
{
    'name': 'Realty Core',
    'version': '19.0.1.1.0',
    'category': 'Realty',
    'summary': 'Master data hub for the Realty Pro suite',
    'description': """
Realty Core
===========

The "Realty Core" application — the master-data layer shared by every
Realty Pro suite (Sales, Project, Living). This module owns:

  - The top-level **Realty Core** menu in the application picker.
  - Submenus under **Master Data**: Projects, Subzones, Buildings,
    Floors, Units, Unit Types.
  - Submenus under **Configuration**: Document Templates, Vendors,
    Vietnamese Administrative Units.

This module contains no business models of its own. It pulls in:

  - ``re_base``: the project / subzone / building / floor / unit
    master tables, plus the lifecycle mixin.
  - ``re_party``: parties (residents, buyers, vendors).
  - ``re_document``: shared document templates.
  - ``re_vendor``: shared vendor / contractor registry.
  - ``vn_administrative_units``: Vietnamese provinces, wards, etc.

Why a separate "core" application?
----------------------------------
Master data is upstream of every operational suite — Sales, Project,
Living all consume the same project / unit records. Putting the master
menus under their own application makes that role explicit, lets the
master-data team work from a dedicated entry point, and keeps the
Sales / Project / Living menus focused on operational work rather
than mixing in setup screens.

Do not depend on this module from operational suites; depend on
``re_base`` (and ``re_party`` etc.) directly. ``re_core`` is a UI
shell, not a code dependency.
""",
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': [
        # re_core is a UI shell that mounts shared master-data screens
        # under a top-level "Realty Core" menu.
        #
        # ``re_base`` holds the property entity tree (project →
        # subzone → building → floor → unit) plus the lifecycle mixin.
        #
        # ``vn_administrative_units`` is referenced by the Wards
        # config menu, so it must load first.
        #
        # ``re_party``, ``re_document``, ``re_vendor`` are *not*
        # listed here even though re_core's Configuration section
        # leaves placeholder slots for them — those modules have no
        # actions to wire up yet. When they do, add them here and
        # uncomment the corresponding <menuitem> records in
        # views/menus.xml.
        're_base',
        'vn_administrative_units',
    ],
    'data': [
        # Categories first — declares the Realty + sub-suite category
        # tree so downstream modules' manifest 'category' paths resolve
        # to the same records.
        'data/categories.xml',
        'views/menus.xml',
    ],
    # Hook runs after data loads. It re-parents any orphan
    # "Realty"-named categories (created automatically by manifest
    # 'category' on modules that load before re_core) onto the
    # canonical XML-tracked records, so the Apps directory shows a
    # single tree instead of two with the same name.
    'post_init_hook': '_post_init_link_categories',
    'application': True,
    'installable': True,
    'auto_install': False,
}
