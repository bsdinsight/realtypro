# -*- coding: utf-8 -*-
"""
Post-migration for re_base 19.0.5.2.0 — Phase 4.0a.

Adds is_open_for_sale Bool field on re.project / re.subzone / re.building.
Field defaults to False on new records (explicit opt-in for new customers).
For existing data already in use BEFORE this migration, set the flag to
True so the current behaviour (units visible on Direct Sales) is
preserved. Owners can subsequently toggle individual records off to
test the gating.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    for table in ('re_project', 're_subzone', 're_building'):
        cr.execute(
            'UPDATE %s SET is_open_for_sale = TRUE '
            'WHERE is_open_for_sale IS DISTINCT FROM TRUE' % table
        )
        _logger.info(
            "Phase 4.0a: set is_open_for_sale=True on %s existing rows in %s",
            cr.rowcount, table,
        )

    # Stored compute re.unit.effective_open_for_sale only reacts to ORM
    # writes. The raw SQL UPDATEs above bypass that hook, so the unit-
    # level rollup column stays stale. Replicate the rollup in SQL here
    # so /api/units/search (which filters on the stored column) returns
    # the right rows immediately after upgrade, without needing to wait
    # for a future ORM write on the unit's parents.
    cr.execute("""
        UPDATE re_unit u
           SET effective_open_for_sale = (
               u.project_id IS NOT NULL
           AND u.building_id IS NOT NULL
           AND EXISTS (SELECT 1 FROM re_project  p
                        WHERE p.id = u.project_id  AND p.is_open_for_sale)
           AND EXISTS (SELECT 1 FROM re_building b
                        WHERE b.id = u.building_id AND b.is_open_for_sale)
           AND (
                   u.subzone_id IS NULL
                OR EXISTS (SELECT 1 FROM re_subzone s
                            WHERE s.id = u.subzone_id AND s.is_open_for_sale)
               )
           )
    """)
    _logger.info(
        "Phase 4.0a: recomputed effective_open_for_sale on %s re.unit rows",
        cr.rowcount,
    )
