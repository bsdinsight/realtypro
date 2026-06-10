# -*- coding: utf-8 -*-
"""
Migration 19.0.1.4.0: rp.tender.package.contractor_id từ rp.contractor
→ res.partner.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute("""
        SELECT contractor_id FROM rp_tender_package
         WHERE contractor_id IS NOT NULL LIMIT 1
    """)
    if not cr.fetchone():
        _logger.info("rp_estimate 19.0.1.4.0: không có data cần migrate.")
        return

    cr.execute("""
        UPDATE res_partner p
           SET is_contractor = TRUE
          FROM rp_contractor c
         WHERE c.partner_id = p.id
           AND c.partner_id IS NOT NULL
    """)

    # NOTE (patched 2026-06-03 by CRM chat, owner-approved):
    # FK constraint must be dropped BEFORE the contractor_id remap, not
    # after. Otherwise UPDATE rp_tender_package SET contractor_id =
    # (a res_partner.id) violates the FK to rp_contractor.id.
    cr.execute("""
        SELECT conname FROM pg_constraint
         WHERE conrelid = 'rp_tender_package'::regclass
           AND contype = 'f'
           AND conname LIKE '%contractor_id%'
    """)
    for (conname,) in cr.fetchall():
        cr.execute("ALTER TABLE rp_tender_package DROP CONSTRAINT IF EXISTS %s"
                   % conname)

    cr.execute("""
        UPDATE rp_tender_package t
           SET contractor_id = c.partner_id
          FROM rp_contractor c
         WHERE t.contractor_id = c.id
           AND c.partner_id IS NOT NULL
    """)
    n = cr.rowcount

    _logger.info(
        "rp_estimate 19.0.1.4.0: remap %s rp.tender.package.contractor_id.", n)
