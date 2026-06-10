# -*- coding: utf-8 -*-
"""
Migration 19.0.1.2.0: rp.contract.contractor_id từ rp.contractor →
res.partner.

Pre-migrate: chuyển dữ liệu FK từ rp.contractor.id sang
rp.contractor.partner_id (= res.partner.id). Đồng thời set
is_contractor=True trên partner để filter domain hoạt động.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # Kiểm tra cột contractor_id còn refer rp_contractor không
    cr.execute("""
        SELECT contractor_id FROM rp_contract WHERE contractor_id IS NOT NULL
        LIMIT 1
    """)
    if not cr.fetchone():
        _logger.info(
            "rp_contract 19.0.1.2.0: không có data contractor_id cần migrate.")
        # Vẫn cần đảm bảo column type đúng — Odoo sẽ tự sync khi load model.
        return

    # 1. Set is_contractor=True cho mọi partner đang được link bởi rp.contractor
    cr.execute("""
        UPDATE res_partner p
           SET is_contractor = TRUE
          FROM rp_contractor c
         WHERE c.partner_id = p.id
           AND c.partner_id IS NOT NULL
    """)
    n_flagged = cr.rowcount

    # 2. UPDATE rp_contract.contractor_id: từ rp_contractor.id → partner_id
    cr.execute("""
        UPDATE rp_contract co
           SET contractor_id = c.partner_id
          FROM rp_contractor c
         WHERE co.contractor_id = c.id
           AND c.partner_id IS NOT NULL
    """)
    n_remapped = cr.rowcount

    _logger.info(
        "rp_contract 19.0.1.2.0: flag is_contractor=True trên %s partner, "
        "remap %s rp_contract.contractor_id từ rp.contractor.id → "
        "res.partner.id.", n_flagged, n_remapped)

    # 3. Drop FK constraint cũ (đến rp_contractor) trước khi Odoo
    # tạo FK mới đến res_partner.
    cr.execute("""
        SELECT conname FROM pg_constraint
         WHERE conrelid = 'rp_contract'::regclass
           AND contype = 'f'
           AND conname LIKE '%contractor_id%'
    """)
    for (conname,) in cr.fetchall():
        cr.execute("ALTER TABLE rp_contract DROP CONSTRAINT IF EXISTS %s"
                   % conname)
        _logger.info("Dropped FK constraint %s", conname)
