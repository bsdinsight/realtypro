# -*- coding: utf-8 -*-
"""
Migration 19.0.1.19.0: backfill original_interest_rate cho KW đã tồn tại.

Bug #3 fix: tách original_interest_rate (immutable) khỏi interest_rate
(current, có thể bị overwrite bởi phụ lục). Để rate cho các kỳ lịch sử
tính đúng, cần backfill original_interest_rate cho mọi KW hiện có.

Logic backfill:
  - Nếu KW chưa có phụ lục rate đã apply → original = interest_rate
    (nhiều khả năng là rate gốc, chưa bị overwrite)
  - Nếu có phụ lục rate đã apply → original = value_old của phụ lục rate
    ĐẦU TIÊN (sorted by date_effective) — vì interest_rate hiện tại đã
    là rate của phụ lục cuối cùng.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # Đảm bảo column đã tồn tại (post-migrate chạy SAU table sync).
    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name='re_loan_note'
           AND column_name='original_interest_rate'
    """)
    if not cr.fetchone():
        _logger.warning(
            "re_loan 19.0.1.19.0: column original_interest_rate "
            "không tồn tại sau table sync — skip migration."
        )
        return

    # 1. KW chưa có phụ lục rate đã apply → original = interest_rate
    cr.execute("""
        UPDATE re_loan_note n
           SET original_interest_rate = n.interest_rate
         WHERE n.original_interest_rate IS NULL
           AND NOT EXISTS (
               SELECT 1 FROM re_loan_note_amendment a
                WHERE a.note_id = n.id
                  AND a.amendment_type = 'rate'
                  AND a.state = 'applied')
    """)
    n_simple = cr.rowcount

    # 2. KW có phụ lục rate đã apply → original = value_old của phụ lục
    # rate ĐẦU TIÊN (sorted asc by date_effective). value_old được lưu
    # dạng '{:.2f}' khi apply (vd "13.00") — cần cast về float.
    cr.execute("""
        WITH first_rate_amend AS (
            SELECT DISTINCT ON (note_id)
                   note_id,
                   value_old
              FROM re_loan_note_amendment
             WHERE amendment_type = 'rate'
               AND state = 'applied'
               AND value_old IS NOT NULL
               AND value_old != ''
          ORDER BY note_id, date_effective ASC, id ASC
        )
        UPDATE re_loan_note n
           SET original_interest_rate =
               CASE
                   WHEN a.value_old ~ '^[0-9]+\\.?[0-9]*$'
                       THEN a.value_old::numeric
                   ELSE n.interest_rate
               END
          FROM first_rate_amend a
         WHERE n.id = a.note_id
           AND n.original_interest_rate IS NULL
    """)
    n_from_amend = cr.rowcount

    _logger.info(
        "re_loan 19.0.1.19.0: backfilled original_interest_rate "
        "cho %s KW (simple) + %s KW (từ value_old phụ lục đầu tiên)",
        n_simple, n_from_amend,
    )
