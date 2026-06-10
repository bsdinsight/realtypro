# -*- coding: utf-8 -*-
"""
Migration 19.0.1.24.0: revert design — interest_rate giờ là rate ký
ban đầu IMMUTABLE. Phụ lục đổi rate KHÔNG còn overwrite field này.

Trước (19.0.1.19.0): tách original_interest_rate khỏi interest_rate;
interest_rate là "current" bị phụ lục overwrite, original giữ rate gốc.

Sau (19.0.1.24.0): bỏ original_interest_rate; interest_rate ĐÃ là rate
gốc immutable. Field original_interest_rate sẽ bị Python remove → cột
DB orphan. Trước khi remove cần restore: với KW đã từng bị overwrite
(interest_rate != original_interest_rate), copy original về interest_rate.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # Chỉ chạy nếu column original_interest_rate còn tồn tại
    # (tức là DB đã qua 19.0.1.19.0 và chưa bị drop).
    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name='re_loan_note'
           AND column_name='original_interest_rate'
    """)
    if not cr.fetchone():
        _logger.info(
            "re_loan 19.0.1.24.0: column original_interest_rate "
            "không tồn tại — fresh install hoặc đã clean, skip."
        )
        return

    # Restore interest_rate = original_interest_rate cho KW đã bị
    # overwrite bởi phụ lục cũ.
    cr.execute("""
        UPDATE re_loan_note
           SET interest_rate = original_interest_rate
         WHERE original_interest_rate IS NOT NULL
           AND original_interest_rate != interest_rate
    """)
    n = cr.rowcount
    _logger.info(
        "re_loan 19.0.1.24.0: restored interest_rate = "
        "original_interest_rate cho %s KW (rate ký ban đầu).",
        n,
    )

    # Drop column original_interest_rate (no longer needed in Python).
    cr.execute("""
        ALTER TABLE re_loan_note
        DROP COLUMN IF EXISTS original_interest_rate
    """)
    _logger.info(
        "re_loan 19.0.1.24.0: dropped column "
        "re_loan_note.original_interest_rate."
    )
