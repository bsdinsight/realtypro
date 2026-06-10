# -*- coding: utf-8 -*-
"""
Migrate guarantee bank fields: Char → Many2one res.partner.

Đổi tên 3 cột `guarantee_*_bank` (Char) → `guarantee_*_bank_id` (M2O).
Cố gắng map giá trị text cũ tới partner (is_bank=True) theo name ilike,
nếu không match → bỏ giá trị (NULL).
"""
import logging

_logger = logging.getLogger(__name__)

OLD_NEW = [
    ('guarantee_performance_bank', 'guarantee_performance_bank_id'),
    ('guarantee_advance_bank', 'guarantee_advance_bank_id'),
    ('guarantee_warranty_bank', 'guarantee_warranty_bank_id'),
]


def migrate(cr, version):
    for old, new in OLD_NEW:
        # Tạo cột mới (Odoo sẽ tự tạo khi load model, nhưng tạo trước
        # để migrate data trong cùng transaction).
        cr.execute(f"""
            ALTER TABLE rp_contract
            ADD COLUMN IF NOT EXISTS {new} INTEGER
        """)
        # Map text → partner.id (ilike)
        cr.execute(f"""
            SELECT id, {old} FROM rp_contract
            WHERE {old} IS NOT NULL AND {old} <> ''
        """)
        rows = cr.fetchall()
        for rec_id, text in rows:
            cr.execute("""
                SELECT id FROM res_partner
                WHERE is_bank = TRUE AND name ILIKE %s
                LIMIT 1
            """, ('%' + text.strip() + '%',))
            match = cr.fetchone()
            if match:
                cr.execute(
                    f"UPDATE rp_contract SET {new}=%s WHERE id=%s",
                    (match[0], rec_id))
                _logger.info("rp.contract %s: %s '%s' → partner %s",
                             rec_id, old, text, match[0])
            else:
                _logger.warning(
                    "rp.contract %s: %s='%s' không match partner is_bank, "
                    "bỏ giá trị.", rec_id, old, text)
        # Drop cột Char cũ
        cr.execute(f"ALTER TABLE rp_contract DROP COLUMN IF EXISTS {old}")
        _logger.info("Dropped column rp_contract.%s", old)
