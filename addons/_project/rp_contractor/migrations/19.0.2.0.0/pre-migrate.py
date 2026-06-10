# -*- coding: utf-8 -*-
"""
Migration 19.0.2.0.0: rp.contractor → _inherits res.partner.

User feedback: chỉ tồn tại 1 bảng nhà thầu cho cả Quản lý vay và
Realty Project. Refactor rp.contractor sang dùng delegation
inheritance — mỗi rp.contractor có 1 res.partner duy nhất.

Pre-migrate đảm bảo TẤT CẢ rp.contractor có partner_id trước khi
model mới (required=True) load.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # Đếm trước
    cr.execute("SELECT COUNT(*) FROM rp_contractor WHERE partner_id IS NULL")
    n_orphan = cr.fetchone()[0]
    _logger.info(
        "rp_contractor 19.0.2.0.0: %s rp.contractor chưa có partner_id, "
        "tạo res.partner mới...", n_orphan)

    # Với mỗi rp.contractor không có partner_id: tạo res.partner mới
    #
    # NOTE (patched 2026-06-03 by CRM chat, owner-approved):
    #   rp_contractor.name is jsonb (translated field in Odoo 19), but
    #   res_partner.name is plain varchar. The original SELECT returned
    #   the raw jsonb dict, which psycopg2 cannot adapt to varchar →
    #   "can't adapt type 'dict'". Extract the localized text in SQL:
    #   prefer vi_VN (this codebase's primary lang), fallback en_US,
    #   then empty string.
    cr.execute("""
        SELECT id,
               COALESCE(name->>'vi_VN', name->>'en_US', ''),
               tax_code, primary_contact_phone,
               primary_contact_email, company_id, headquarters_address
        FROM rp_contractor
        WHERE partner_id IS NULL
    """)
    rows = cr.fetchall()
    for rec_id, name, tax_code, phone, email, company_id, address in rows:
        # NOTE (patched 2026-06-03 by CRM chat, owner-approved):
        # res_partner.autopost_bills is NOT NULL (no default at DB level)
        # in Odoo 19. Raw SQL INSERT must supply it explicitly. 'ask'
        # mirrors the ORM-level Selection default.
        cr.execute("""
            INSERT INTO res_partner
                (name, vat, phone, email, street, is_company, active,
                 company_id, create_date, write_date, create_uid, write_uid,
                 lang, autopost_bills)
            VALUES (%s, %s, %s, %s, %s, TRUE, TRUE, %s,
                    NOW(), NOW(), 1, 1, 'vi_VN', 'ask')
            RETURNING id
        """, (name, tax_code, phone, email, address, company_id))
        new_partner_id = cr.fetchone()[0]
        cr.execute(
            "UPDATE rp_contractor SET partner_id = %s WHERE id = %s",
            (new_partner_id, rec_id))

    # Đồng bộ tên: với rp.contractor đã có partner_id, sync name về
    # partner.name (nếu partner.name khác). Để inherit delegation
    # hoạt động đúng ở UI.
    #
    # Same jsonb→varchar extraction as above on c.name.
    cr.execute("""
        UPDATE res_partner p
           SET name = COALESCE(c.name->>'vi_VN', c.name->>'en_US', '')
          FROM rp_contractor c
         WHERE c.partner_id = p.id
           AND COALESCE(p.name, '')
            != COALESCE(c.name->>'vi_VN', c.name->>'en_US', '')
    """)
    n_synced = cr.rowcount
    _logger.info(
        "rp_contractor 19.0.2.0.0: created %s partners + synced name "
        "for %s existing partners. All rp.contractor giờ có partner_id.",
        len(rows), n_synced)
