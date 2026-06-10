# -*- coding: utf-8 -*-
"""
Migration 19.0.1.27.0: TSBĐ pledge — chuyển từ KW-level → HĐTD-level.

Trước: pledge có thể có note_id hoặc credit_contract_id (1 trong 2).
Practice thực tế: phần lớn user đăng ký pledge ở KW level (kế hoạch
ban đầu) — nhưng đúng nghiệp vụ VN, pledge nên ở HĐTD level.

Migration:
  1. Thêm column pledge_target (Selection) + facility_id (M2O) nếu
     chưa tồn tại.
  2. Với mỗi pledge cũ có note_id set:
       - Tìm note.facility_id.credit_contract_id
       - Set pledge_target='contract', credit_contract_id=that contract
       - Clear note_id (promote lên contract level)
       - DEDUP: nếu cùng (asset, contract) đã có pledge active khác
         thì giữ pledge cũ nhất, các pledge sau đánh dấu released với
         lý do "merged in migration"
  3. Pledge cũ có credit_contract_id set + không note_id → target='contract'
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # 1. Ensure new columns exist (Odoo sẽ ADD COLUMN khi load model,
    #    nhưng pre-migrate chạy TRƯỚC — em chủ động ADD để UPDATE
    #    sau đó không lỗi).
    cr.execute("""
        ALTER TABLE re_loan_collateral_pledge
        ADD COLUMN IF NOT EXISTS pledge_target VARCHAR;
    """)
    cr.execute("""
        ALTER TABLE re_loan_collateral_pledge
        ADD COLUMN IF NOT EXISTS facility_id INTEGER;
    """)

    # 2. Promote pledge có note_id → contract level
    cr.execute("""
        UPDATE re_loan_collateral_pledge p
           SET credit_contract_id = COALESCE(
                   p.credit_contract_id,
                   f.credit_contract_id),
               pledge_target = 'contract',
               note_id = NULL
          FROM re_loan_note n
          JOIN re_loan_facility f ON n.facility_id = f.id
         WHERE p.note_id = n.id
           AND p.note_id IS NOT NULL
    """)
    promoted = cr.rowcount
    _logger.info(
        "re_loan 19.0.1.27.0: promoted %s pledge(s) từ KW → HĐTD level",
        promoted)

    # 3. Pledge có credit_contract_id (cấp HĐTD vốn dĩ) → target='contract'
    cr.execute("""
        UPDATE re_loan_collateral_pledge
           SET pledge_target = 'contract'
         WHERE pledge_target IS NULL
           AND credit_contract_id IS NOT NULL
    """)
    contract_level = cr.rowcount
    _logger.info(
        "re_loan 19.0.1.27.0: set pledge_target='contract' cho %s "
        "pledge sẵn ở cấp HĐTD",
        contract_level)

    # 4. Dedup: nếu cùng (collateral_id, credit_contract_id) có > 1
    #    pledge active, giữ pledge cũ nhất, các pledge sau release.
    cr.execute("""
        WITH dups AS (
            SELECT id, collateral_id, credit_contract_id,
                   ROW_NUMBER() OVER (
                       PARTITION BY collateral_id, credit_contract_id
                       ORDER BY date_pledge, id
                   ) AS rn
              FROM re_loan_collateral_pledge
             WHERE state = 'active'
               AND credit_contract_id IS NOT NULL
        )
        UPDATE re_loan_collateral_pledge p
           SET state = 'released',
               release_reason = 'Merged in migration 19.0.1.27.0 — '
                                'duplicate after KW→Contract promotion'
          FROM dups d
         WHERE p.id = d.id
           AND d.rn > 1
    """)
    deduped = cr.rowcount
    _logger.info(
        "re_loan 19.0.1.27.0: dedup released %s pledge trùng "
        "(asset × contract).",
        deduped)
