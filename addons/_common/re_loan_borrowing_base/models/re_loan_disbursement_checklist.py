# -*- coding: utf-8 -*-
"""Checklist 8 điều kiện giải ngân — tài liệu nghiệp vụ §7 / spec team khối 2 mục 5.

Checklist sống trên KW (spec: "KW: ràng buộc chấp thuận giải ngân khi đủ
các điều kiện"); CHẶN tại `action_submit` của đợt giải ngân (lúc trình
ngân hàng — tài liệu nghiệp vụ: "một đợt giải ngân chỉ được DUYỆT khi đồng thời...").
Nháp tạo thoải mái để chuẩn bị hồ sơ; trình mới soát. Gate vốn tự có
(mục 2) vẫn chặn sớm từ lúc TẠO ("tạm dừng đề xuất").

Chỉ áp cho KW CÓ GẮN DỰ ÁN (trục nghiệp vụ) — KW cũ không gắn dự án giữ nguyên
hành vi.

5 điều kiện AUTO từ dữ liệu:
  1. HĐ xây lắp còn hiệu lực (owner contract signed/executing)
  2. Hồ sơ khối lượng hợp lệ (dự án có IPC đã được CĐT ký)
  3. Đủ vốn tự có (phiếu Nhu cầu vốn — chưa lập phiếu = cảnh báo, không chặn)
  4. Không vượt ngân sách (EVM: AC ≤ BAC)
  6. Không có nợ quá hạn chưa xử lý (không KW nào state=overdue cùng công ty)
  8. Chống tài trợ trùng (ràng buộc máy đã có: BBNT→1 IPC duy nhất,
     IPC không cầm cố 2 lần — auto đạt, ghi rõ phạm vi trong help)

2 điều kiện TICK TAY (chưa có model tự kiểm):
  5. Không vi phạm covenant
  7. Dòng tiền về đúng TK kiểm soát của NH — TỰ ĐỘNG khi HĐTD khai số TK
     kiểm soát VÀ có dữ liệu đối soát ngân hàng; không thì tick tay.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ReLoanCreditContractControlledAccount(models.Model):
    _inherit = 're.loan.credit.contract'

    controlled_account = fields.Char(
        string='TK kiểm soát dòng tiền (NH)',
        help='Số tài khoản ngân hàng chỉ định nhận tiền CĐT thanh toán. '
             'Khai vào đây để hệ thống TỰ ĐỐI CHIẾU giao dịch tiền về '
             '(đối soát ngân hàng) với điều kiện giải ngân số 7.')


class ReLoanNoteChecklist(models.Model):
    _inherit = 're.loan.note'

    # ── auto ──
    chk_contract_active = fields.Boolean(
        string='1. HĐ xây lắp còn hiệu lực', compute='_compute_checklist',
        help='Dự án có HĐ với CĐT ở trạng thái Đã ký / Đang thi công.')
    chk_volume_docs = fields.Boolean(
        string='2. Hồ sơ khối lượng hợp lệ', compute='_compute_checklist',
        help='Dự án có ít nhất một IPC đã được CĐT ký nhận.')
    chk_equity = fields.Selection(
        [('ok', 'Đủ'), ('short', 'THIẾU'), ('no_sheet', 'Chưa lập phiếu')],
        string='3. Vốn tự có', compute='_compute_checklist',
        help='Theo phiếu Nhu cầu vốn dự án. "Chưa lập phiếu" = cảnh báo, '
             'không chặn (opt-in).')
    chk_budget = fields.Boolean(
        string='4. Không vượt ngân sách', compute='_compute_checklist',
        help='EVM: chi phí đã thực hiện (AC) ≤ tổng dự toán (BAC).')
    chk_no_overdue = fields.Boolean(
        string='6. Không có nợ quá hạn', compute='_compute_checklist',
        help='Không khế ước nào của công ty đang ở trạng thái Quá hạn.')
    chk_no_double_finance = fields.Boolean(
        string='8. Chống tài trợ trùng', compute='_compute_checklist',
        help='Ràng buộc máy đang bật: mỗi BBNT chỉ vào một IPC; mỗi IPC '
             'chỉ cầm cố một lần; TSBĐ cấp HĐ chỉ tính phần chưa cầm cố '
             'theo IPC.')
    chk_funds_account = fields.Selection(
        [('ok', 'Khớp'), ('mismatch', 'SAI TK'), ('manual', 'Tự xác nhận')],
        string='7. Tiền về đúng TK kiểm soát', compute='_compute_checklist',
        help='TỰ ĐỘNG khi HĐTD khai TK kiểm soát và có giao dịch đối soát '
             'ngân hàng của IPC dự án; nếu chưa khai TK → dùng ô tick tay.')

    # ── tick tay ──
    chk_covenant_manual = fields.Boolean(
        string='5. Không vi phạm covenant (xác nhận)', tracking=True,
        help='Tick sau khi rà các điều kiện tín dụng của HĐTD. (Model '
             'covenant tự kiểm là hạng mục lộ trình.)')
    chk_funds_manual = fields.Boolean(
        string='7. Tiền về đúng TK (xác nhận tay)', tracking=True,
        help='Chỉ dùng khi HĐTD CHƯA khai TK kiểm soát để hệ thống tự '
             'đối chiếu.')

    chk_summary = fields.Char(
        string='Điều kiện giải ngân', compute='_compute_checklist')

    # Cảnh báo mềm về NĂNG LỰC TRẢ NỢ (§8) nằm ở
    # models/re_loan_repayment_capacity.py — 5 tín hiệu, không chặn.

    @api.depends('project_id', 'facility_id', 'state',
                 'chk_covenant_manual', 'chk_funds_manual')
    def _compute_checklist(self):
        Contract = self.env['rp.owner.contract']
        Ipc = self.env['rp.owner.ipc']
        Funding = self.env['re.loan.project.funding']
        Note = self.env['re.loan.note']
        has_bank_sync = 're.bank.transaction' in self.env
        for rec in self:
            proj = rec.project_id
            if not proj:
                rec.update({
                    'chk_contract_active': False, 'chk_volume_docs': False,
                    'chk_equity': 'no_sheet', 'chk_budget': False,
                    'chk_no_overdue': False,
                    'chk_no_double_finance': False,
                    'chk_funds_account': 'manual',
                    'chk_summary': _('KW chưa gắn dự án — checklist '
                                     'không áp dụng')})
                continue

            # 1. HĐ còn hiệu lực
            c1 = bool(Contract.search_count(
                [('project_id', '=', proj.id),
                 ('state', 'in', ('signed', 'executing'))]))
            # 2. có IPC CĐT ký
            c2 = bool(Ipc.search_count(
                [('project_id', '=', proj.id), ('state', '=', 'signed')]))
            # 3. vốn tự có (phiếu nhu cầu vốn)
            sheet = Funding.search(
                [('project_id', '=', proj.id)], limit=1)
            c3 = ('no_sheet' if not sheet
                  else 'ok' if sheet.equity_ok else 'short')
            # 4. ngân sách: AC ≤ BAC
            c4 = (proj.total_ac or 0.0) <= (proj.total_bac or 0.0) + 0.01
            # 6. nợ quá hạn toàn công ty
            c6 = not Note.search_count(
                [('state', '=', 'overdue'),
                 ('company_id', '=', rec.company_id.id)])
            # 7. tiền về đúng TK kiểm soát
            cc = rec.facility_id.credit_contract_id
            acct = (cc.controlled_account or '').strip() if cc else ''
            if acct and has_bank_sync:
                Txn = self.env['re.bank.transaction']
                wrong = Txn.search_count(
                    [('direction', '=', 'in'),
                     ('state', '=', 'reconciled'),
                     ('ipc_id.project_id', '=', proj.id),
                     ('account_number', '!=', acct)])
                c7 = 'mismatch' if wrong else 'ok'
            else:
                c7 = 'manual'
            # 8. chống trùng — ràng buộc máy đang bật
            c8 = True

            rec.chk_contract_active = c1
            rec.chk_volume_docs = c2
            rec.chk_equity = c3
            rec.chk_budget = c4
            rec.chk_no_overdue = c6
            rec.chk_no_double_finance = c8
            rec.chk_funds_account = c7

            fails = rec._checklist_failures()
            rec.chk_summary = (_('ĐẠT %d/8 — sẵn sàng trình NH')
                               % 8 if not fails else
                               _('CHƯA ĐẠT %d điều kiện') % len(fails))

    def _checklist_failures(self):
        """Danh sách điều kiện CHƯA ĐẠT (chuỗi mô tả). Rỗng = đạt hết."""
        self.ensure_one()
        fails = []
        if not self.chk_contract_active:
            fails.append(_('1. Hợp đồng xây lắp của dự án không còn hiệu '
                           'lực (cần Đã ký / Đang thi công)'))
        if not self.chk_volume_docs:
            fails.append(_('2. Dự án chưa có IPC nào được CĐT ký nhận '
                           '(hồ sơ khối lượng)'))
        if self.chk_equity == 'short':
            fails.append(_('3. Góp thiếu vốn tự có theo phiếu Nhu cầu '
                           'vốn dự án'))
        if not self.chk_budget:
            fails.append(_('4. Chi phí đã thực hiện VƯỢT tổng dự toán '
                           '(EVM)'))
        if not self.chk_covenant_manual:
            fails.append(_('5. Chưa xác nhận "không vi phạm covenant" '
                           '(tick trên KW)'))
        if not self.chk_no_overdue:
            fails.append(_('6. Công ty đang có khế ước QUÁ HẠN chưa xử lý'))
        if self.chk_funds_account == 'mismatch':
            fails.append(_('7. Có giao dịch tiền CĐT về KHÔNG ĐÚNG tài '
                           'khoản kiểm soát của NH'))
        elif self.chk_funds_account == 'manual' \
                and not self.chk_funds_manual:
            fails.append(_('7. Chưa xác nhận "tiền về đúng TK kiểm soát" '
                           '(khai TK trên HĐTD để tự kiểm, hoặc tick tay '
                           'trên KW)'))
        return fails


class ReLoanNoteDisbursementChecklistGate(models.Model):
    _inherit = 're.loan.note.disbursement'

    def action_submit(self):
        for disb in self:
            note = disb.note_id
            if note.project_id:
                fails = note._checklist_failures()
                if fails:
                    raise UserError(_(
                        'CHƯA ĐỦ ĐIỀU KIỆN TRÌNH GIẢI NGÂN (tài liệu nghiệp vụ §7) — '
                        'KW %(kw)s, dự án %(p)s:\n\n• %(f)s',
                        kw=note.name, p=note.project_id.display_name,
                        f='\n• '.join(fails)))
        return super().action_submit()
