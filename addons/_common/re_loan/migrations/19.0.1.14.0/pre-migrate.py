# -*- coding: utf-8 -*-
"""
Migration 19.0.1.14.0: chuyển `flexible_limits` từ HĐTD (re.loan.credit.contract)
sang từng facility (re.loan.facility).

Trước: flag duy nhất trên HĐTD → tất cả facility con cùng theo.
Sau:   flag riêng từng facility → chỉ facility tick mới chia pool với nhau,
       facility không tick giữ limit cứng. Σ limit luôn ≤ HĐTD (hard rule).
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # 1. Kiểm tra column cũ trên contract còn tồn tại không.
    cr.execute("""
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 're_loan_credit_contract'
          AND column_name = 'flexible_limits'
    """)
    contract_has_flex = bool(cr.fetchone())

    # 2. Tạo column mới trên facility (idempotent).
    cr.execute("""
        ALTER TABLE re_loan_facility
        ADD COLUMN IF NOT EXISTS flexible_limits BOOLEAN DEFAULT FALSE
    """)

    # 3. Nếu contract còn flag cũ → set tất cả facility con = TRUE.
    if contract_has_flex:
        cr.execute("""
            UPDATE re_loan_facility f
               SET flexible_limits = TRUE
              FROM re_loan_credit_contract c
             WHERE f.credit_contract_id = c.id
               AND c.flexible_limits = TRUE
        """)
        affected = cr.rowcount
        _logger.info(
            "re_loan 19.0.1.14.0: backfilled flexible_limits=TRUE on "
            "%s facility(ies) from HĐTD parent",
            affected,
        )

        # 4. Xoá column cũ trên contract (an toàn vì giá trị đã copy xong).
        cr.execute("""
            ALTER TABLE re_loan_credit_contract
            DROP COLUMN IF EXISTS flexible_limits
        """)
        _logger.info(
            "re_loan 19.0.1.14.0: dropped legacy column "
            "re_loan_credit_contract.flexible_limits"
        )
    else:
        _logger.info(
            "re_loan 19.0.1.14.0: contract.flexible_limits column not "
            "found — fresh install, skipping backfill"
        )
