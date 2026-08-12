# -*- coding: utf-8 -*-
"""Nhu cầu vốn dự án — form (1)→(8) theo spec nghiệp vụ mục 3 + §9.

Công thức (đã chốt với anh Đại — theo tài liệu nghiệp vụ gốc §9.4, spec team ghi thiếu
trừ vốn tự có do đánh số nhầm):

  (1) Cost to Complete  = BAC − AC            (EVM, tự động)
  (2) Vốn tự có phải góp = CTC × tỷ lệ cam kết
  (3) Tạm ứng CĐT còn khả dụng               (owner contract, tự động)
  (4) Công nợ NCC được trả chậm              (khai — hạn mức thương mại)
  (5) Nhu cầu vay thêm  = (1) − (2) − (3) − (4)
  (8) Chưa được tài trợ = (5) − Σ hạn mức CÒN LẠI đã phân bổ cho dự án

Lưu ý (8): theo VÍ DỤ SỐ của tài liệu nghiệp vụ (§9.7: 436 − 250 = 186, với 250 = phần
hạn mức CÒN LẠI chưa rút), không phải "tổng hạn mức" như câu chữ spec team
— hai bản mâu thuẫn nhau, số của tài liệu nghiệp vụ thắng.

CHẶN GIẢI NGÂN (2): dự án có phiếu nhu cầu vốn mà thực góp < cam kết →
không cho tạo giải ngân mới trên KW của dự án đó (tài liệu nghiệp vụ §3: "tạm dừng đề
xuất giải ngân thêm cho đến khi bổ sung"). Opt-in: dự án CHƯA lập phiếu
thì không bị chặn (không phá dữ liệu cũ).
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ReLoanProjectFunding(models.Model):
    _name = 're.loan.project.funding'
    _description = 'Nhu cầu vốn dự án (form 1-8 theo tài liệu nghiệp vụ)'
    _inherit = ['mail.thread']
    _rec_name = 'display_name'

    project_id = fields.Many2one(
        're.project', string='Dự án', required=True, index=True,
        ondelete='restrict', tracking=True)
    company_id = fields.Many2one(
        'res.company', default=lambda s: s.env.company)
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda s: s.env.company.currency_id)

    # ── (1) Cost to Complete — EVM, tự động ──────────────────────────
    amount_bac = fields.Monetary(
        string='Tổng dự toán (BAC)', compute='_compute_ctc',
        help='Σ giá trị dự toán các hạng mục của dự án (EVM). Dùng dự '
             'toán ĐIỀU CHỈNH — phát sinh/VO duyệt phải cập nhật vào BOQ.')
    amount_ac = fields.Monetary(
        string='Chi phí đã thực hiện (AC)', compute='_compute_ctc')
    cost_excluded = fields.Monetary(
        string='Loại trừ khỏi CTC', tracking=True,
        help='Tài liệu nghiệp vụ §3: CTC chỉ gồm khoản THỰC SỰ phát sinh dòng '
             'tiền và có hồ sơ hợp lệ. Khai ở đây phần phải LOẠI khỏi '
             '(BAC − AC): lợi nhuận dự kiến còn nằm trong dự toán, khấu '
             'hao, chi phí đã thanh toán nhưng chưa ghi nhận AC, chi phí '
             'đang tranh chấp hoặc chưa được phê duyệt.')
    cost_excluded_note = fields.Char(
        string='Diễn giải loại trừ',
        help='Ghi rõ loại trừ khoản nào — ngân hàng sẽ hỏi.')
    cost_to_complete = fields.Monetary(
        string='① Chi phí còn phải chi (CTC)', compute='_compute_ctc',
        help='= BAC − AC. Chỉ gồm khoản thực phát sinh dòng tiền, hồ sơ '
             'hợp lệ — không gồm lợi nhuận dự kiến, khấu hao, tranh chấp.')

    # ── (2) Vốn tự có ────────────────────────────────────────────────
    equity_rate_pct = fields.Float(
        string='Tỷ lệ vốn tự có cam kết (%)', tracking=True,
        help='Do ngân hàng ấn định theo xếp hạng tín dụng / chất lượng '
             'CĐT / rủi ro công trình — khai theo TỪNG dự án.')
    equity_base = fields.Selection(
        [('bac', 'Tổng dự toán dự án (BAC)'),
         ('ctc', 'Chi phí còn phải chi (CTC)')],
        string='Tính vốn tự có trên', default='bac', required=True,
        tracking=True,
        help='BAC = % trên TOÀN BỘ dự toán dự án (anh Đại 2026-08-10, và '
             'là thông lệ NH: "vốn tự có tối thiểu x% tổng mức đầu tư").\n'
             'CTC = % trên phần CÒN PHẢI CHI — đúng ví dụ §9.3 tài liệu '
             'tổng thầu (720 × 20%% = 144 tỷ). Hai gốc cho số khác nhau khi dự '
             'án đã phát sinh chi phí (AC > 0).')
    exclude_contingency = fields.Boolean(
        string='Loại dự phòng khỏi CTC', default=True, tracking=True,
        help='Tài liệu nghiệp vụ §3: CTC chỉ gồm khoản THỰC SỰ phát sinh dòng '
             'tiền và có hồ sơ hợp lệ — dự phòng chưa phát sinh.\n'
             'Tắt nếu ngân hàng muốn tính cả dự phòng vào nhu cầu vốn.')
    exclude_finance_cost = fields.Boolean(
        string='Loại chi phí tài chính khỏi CTC', default=True,
        tracking=True,
        help='Tránh VÒNG LẶP: vay → lãi vay → tăng CTC → tăng nhu cầu '
             'vay.\nTắt nếu hồ sơ tính lãi vay trong thời gian xây dựng '
             'vào tổng mức đầu tư.')
    amount_contingency = fields.Monetary(
        string='Trừ: dự phòng', compute='_compute_ctc',
        help='Σ dự toán các nhóm mang cờ "Dự phòng" (theo cờ trên danh '
             'mục, không theo mã cứng).')
    amount_finance_cost = fields.Monetary(
        string='Trừ: chi phí tài chính', compute='_compute_ctc',
        help='Σ dự toán các nhóm mang cờ "Chi phí tài chính".')
    amount_finance_contingency = fields.Monetary(
        string='Trừ: tài chính + dự phòng', compute='_compute_ctc',
        help='Tổng hai khoản trên — dùng cho cả CTC lẫn gốc tính vốn tự '
             'có.')

    def _flagged_total(self, flag):
        """Σ dự toán các nhóm mang cờ, chỉ lấy ĐỈNH của nhánh có cờ để
        không cộng trùng cha + con (est_total đã roll-up con)."""
        self.ensure_one()
        if not self.project_id or 'rp.cost.category' not in self.env:
            return 0.0
        Cat = self.env['rp.cost.category']
        if flag not in Cat._fields:
            return 0.0
        cats = Cat.search([('project_id', '=', self.project_id.id),
                           (flag, '=', True)])
        tops = cats.filtered(
            lambda c: not c.parent_id or not c.parent_id[flag])
        return sum(tops.mapped('est_total'))
    equity_base_amount = fields.Monetary(
        string='Gốc tính vốn tự có', compute='_compute_need',
        help='BAC ĐIỀU CHỈNH (= BAC − nhóm 09 − nhóm 10) hoặc CTC, tuỳ '
             'lựa chọn ở trên.')
    equity_in_kind = fields.Monetary(
        string='Góp bằng hiện vật (đất/tài sản)', tracking=True,
        help='Rất phổ biến ở VN: chủ đầu tư góp bằng quyền sử dụng đất '
             'hoặc tài sản. Không ghi ở đây thì tỷ lệ vốn tự có hiện '
             'thiếu một cách giả tạo.')
    equity_in_kind_note = fields.Char(
        string='Diễn giải hiện vật',
        help='Vd "QSDĐ thửa 123, định giá theo chứng thư ABC ngày ...".')
    equity_contributed_total = fields.Monetary(
        string='Tổng đã góp (tiền + hiện vật)', compute='_compute_need')
    equity_used = fields.Monetary(
        string='Vốn tự có ĐÃ DÙNG trả NCC', compute='_compute_equity_cash',
        help='Σ các mốc thanh toán HĐ nhà thầu của dự án chọn nguồn = '
             'Vốn tự có (kể cả phần chia nhiều nguồn).')
    equity_cash_left = fields.Monetary(
        string='Vốn tự có CÒN LẠI', compute='_compute_equity_cash',
        help='= Vốn tự có thực góp bằng TIỀN − đã dùng trả nhà thầu/NCC. '
             'Góp bằng hiện vật (đất) không tính ở đây vì không tiêu '
             'được để trả nhà thầu.')

    @api.depends('project_id', 'equity_contributed')
    def _compute_equity_cash(self):
        Ms = self.env['rp.contract.payment.milestone']
        has = 'funding_source' in Ms._fields
        for r in self:
            used = 0.0
            if has and r.project_id:
                cands = Ms.search([
                    ('contract_id.project_id', '=', r.project_id.id)])
                for m in cands:
                    if hasattr(m, '_amount_from_source'):
                        used += m._amount_from_source('equity')
                    elif m.funding_source == 'equity':
                        used += m.amount or 0.0
            r.equity_used = used
            r.equity_cash_left = max(
                0.0, (r.equity_contributed or 0.0) - used)
    equity_required = fields.Monetary(
        string='② Vốn tự có phải góp', compute='_compute_need',
        help='= Gốc tính × tỷ lệ cam kết.')
    equity_to_contribute = fields.Monetary(
        string='Vốn tự có CÒN PHẢI GÓP', compute='_compute_need',
        help='= Phải góp − Đã thực góp. Khi tính trên BAC thì ĐÂY mới là '
             'số trừ vào Nhu cầu vay — phần đã góp đã nằm trong chi phí '
             'đã thực hiện (AC), trừ cả tổng sẽ là trừ hai lần.')
    equity_contributed = fields.Monetary(
        string='Vốn tự có THỰC GÓP', tracking=True,
        help='Số đã góp thật. Thiếu so với cam kết → hệ thống CHẶN tạo '
             'giải ngân mới cho dự án này.')
    equity_shortfall = fields.Monetary(
        string='Thiếu vốn tự có', compute='_compute_need')
    equity_ok = fields.Boolean(compute='_compute_need')

    # ── (3) Tạm ứng CĐT còn khả dụng — tự động ───────────────────────
    advance_available = fields.Monetary(
        string='③ Tạm ứng CĐT còn khả dụng', compute='_compute_need',
        help='Σ tiền tạm ứng CĐT CÒN TRONG TÀI KHOẢN của dự án = đã '
             'nhận − đã dùng trả nhà thầu/NCC. Tự động.\n'
             'KHÁC với "còn phải hoàn CĐT" (mặt nợ, bị khấu trừ '
             'dần qua BBNT) — xem hai cột đó trên phiếu tạm ứng.')

    # ── (4) NCC trả chậm — khai ──────────────────────────────────────
    # ── ④ tách 3 nguồn: hoá đơn chưa đến hạn + giữ lại thầu phụ + khai tay
    supplier_credit_invoiced = fields.Monetary(
        string='Hoá đơn NCC chưa đến hạn', compute='_compute_supplier_credit',
        help='Σ số CÒN PHẢI TRẢ của hoá đơn nhà thầu/NCC đã ghi sổ, chưa '
             'thanh toán và CHƯA tới hạn. Đây là nguồn vốn thật: hàng/khối '
             'lượng đã nhận mà chưa phải xuất tiền. Hoá đơn QUÁ HẠN không '
             'tính vào đây.')
    supplier_credit_retention = fields.Monetary(
        string='Giữ lại của thầu phụ', compute='_compute_supplier_credit',
        help='Σ tiền giữ lại (retention) theo HĐ nhà thầu, tính theo tiến '
             'độ đã thanh toán — tiền nằm trong túi mình suốt thời gian '
             'thi công nên là nguồn trả chậm rõ ràng nhất.')
    supplier_advance_paid = fields.Monetary(
        string='⑥ Tạm ứng ĐÃ CHI cho thầu phụ',
        compute='_compute_supplier_credit',
        help='Tiền đã ứng trước cho thầu phụ/NCC và CHƯA thu hồi. Khối '
             'lượng chưa nghiệm thu nên chi phí đó vẫn nằm nguyên trong '
             'CTC, trong khi tiền đã ra khỏi túi ⇒ CTC kê THỪA đúng bằng '
             'số này. Vì vậy nó LÀM GIẢM nhu cầu vay.\n'
             '⚠ Chỉ đúng khi tạm ứng CHƯA được ghi vào Chi phí đã thực '
             'hiện (AC). Nếu kế toán bắt đầu ghi tạm ứng vào AC thì CTC '
             'đã trừ một lần — phải bỏ dòng này, kẻo trừ hai lần.')
    supplier_credit_overdue = fields.Monetary(
        string='⚠ Công nợ NCC QUÁ HẠN', compute='_compute_supplier_credit',
        help='KHÔNG tính là nguồn vốn. Đây là cảnh báo — ngân hàng nhìn '
             'vào con số này khi thẩm định.')
    supplier_credit_total = fields.Monetary(
        string='④ Công nợ NCC được trả chậm',
        compute='_compute_supplier_credit',
        help='= Hoá đơn chưa đến hạn + Giữ lại thầu phụ − Tạm ứng đã chi '
             '+ Khai tay bổ sung.')
    supplier_credit = fields.Monetary(
        string='④ Khai tay bổ sung', tracking=True,
        help='Hạn mức tín dụng thương mại NCC đã thoả thuận (60-90 '
             'ngày...) — phần chi CHƯA cần tiền ngay. Khai tay giai đoạn '
             'đầu; sau nối công nợ kế toán.')

    # ── (5) + (8) ────────────────────────────────────────────────────
    funding_need = fields.Monetary(
        string='⑤ Nhu cầu vay thêm', compute='_compute_need',
        help='= ① − ② − ③ − ④ (floor 0).')
    limit_allocated = fields.Monetary(
        string='Σ hạn mức phân bổ cho dự án', compute='_compute_limits')
    limit_used = fields.Monetary(
        string='Σ dư nợ dự án', compute='_compute_limits')
    limit_remaining = fields.Monetary(
        string='Σ hạn mức còn lại', compute='_compute_limits')
    available_now = fields.Monetary(
        string='Σ khả dụng rút ngay', compute='_compute_limits',
        help='Σ khả dụng theo dự án trên các facility (đã trừ ràng buộc '
             'TSBĐ). Chỉ dẫn — các bể chung độc lập theo từng facility.')
    unfunded_need = fields.Monetary(
        string='⑧ Nhu cầu CHƯA được tài trợ', compute='_compute_need',
        help='= ⑤ Nhu cầu vay thêm − Σ dư nợ ĐÃ GIẢI NGÂN cho dự án '
             '(tài liệu nghiệp vụ §9.7: 436 − 250 đã giải ngân = 186). Con số '
             'đi ĐÀM PHÁN THÊM hạn mức — theo dõi song song, KHÔNG nằm '
             'trong công thức khả dụng.')

    allocation_ids = fields.Many2many(
        're.loan.facility.project.allocation', string='Phân bổ hạn mức',
        compute='_compute_limits')
    note = fields.Text(string='Ghi chú')
    active = fields.Boolean(default=True)

    _uniq_project = models.Constraint(
        'unique(project_id)',
        'Mỗi dự án chỉ có một phiếu Nhu cầu vốn — cập nhật phiếu hiện có.')

    @api.depends('project_id')
    def _compute_display_name(self):
        for r in self:
            r.display_name = _('Nhu cầu vốn — %s') % (
                r.project_id.display_name or '')

    @api.depends('project_id')
    def _compute_supplier_credit(self):
        """④ lấy tự động từ hoá đơn NCC + giữ lại thầu phụ, trừ tạm ứng."""
        Move = self.env['account.move']
        Contract = self.env['rp.contract'] if 'rp.contract' in self.env \
            else None
        Adv = (self.env['rp.advance.payment']
               if 'rp.advance.payment' in self.env else None)
        today = fields.Date.context_today(self)
        for r in self:
            inv = due = 0.0
            if r.project_id and 'project_id' in Move._fields:
                moves = Move.search([
                    ('move_type', '=', 'in_invoice'),
                    ('state', '=', 'posted'),
                    ('project_id', '=', r.project_id.id),
                    ('payment_state', 'not in', ('paid', 'reversed'))])
                for m in moves:
                    if m.invoice_date_due and m.invoice_date_due < today:
                        due += abs(m.amount_residual)
                    else:
                        inv += abs(m.amount_residual)
            ret = 0.0
            if Contract is not None and r.project_id:
                for ct in Contract.search(
                        [('project_id', '=', r.project_id.id)]):
                    # giữ lại theo TIẾN ĐỘ đã thanh toán, không lấy trọn HĐ
                    ratio = ((ct.amount_paid / ct.contract_value_total)
                             if ct.contract_value_total else 0.0)
                    ret += (ct.amount_retention or 0.0) * min(1.0, ratio)
            adv = 0.0
            if Adv is not None and r.project_id:
                adv = sum(Adv.search([
                    ('contract_id.project_id', '=', r.project_id.id),
                    ('state', 'not in', ('cancelled', 'draft')),
                ]).mapped('amount_remaining'))
            r.supplier_credit_invoiced = inv
            r.supplier_credit_overdue = due
            r.supplier_credit_retention = ret
            r.supplier_advance_paid = adv
            # ④ chỉ gồm khoản DƯƠNG → không cần kẹp 0. Tạm ứng đã chi
            # cho thầu phụ KHÔNG trừ ở đây nữa mà tách thành ⑥ (xem
            # _compute_need): nó là tiền ĐÃ BỎ RA, làm GIẢM nhu cầu vay.
            r.supplier_credit_total = inv + ret + (r.supplier_credit or 0.0)

    @api.depends('project_id', 'project_id.total_bac',
                 'project_id.total_ac', 'cost_excluded',
                 'exclude_contingency', 'exclude_finance_cost')
    def _compute_ctc(self):
        for r in self:
            bac = r.project_id.total_bac or 0.0
            ac = r.project_id.total_ac or 0.0
            r.amount_bac = bac
            r.amount_ac = ac
            # §3: trừ phần KHÔNG phải dòng tiền / chưa hợp lệ
            cont = r._flagged_total('is_contingency')
            fin = r._flagged_total('is_finance_cost')
            r.amount_contingency = cont
            r.amount_finance_cost = fin
            r.amount_finance_contingency = cont + fin
            drop = ((cont if r.exclude_contingency else 0.0)
                    + (fin if r.exclude_finance_cost else 0.0))
            r.cost_to_complete = max(
                0.0, bac - ac - drop - (r.cost_excluded or 0.0))

    @api.depends('project_id')
    def _compute_limits(self):
        Alloc = self.env['re.loan.facility.project.allocation']
        for r in self:
            allocs = Alloc.search(
                [('project_id', '=', r.project_id.id)]) \
                if r.project_id else Alloc
            r.allocation_ids = allocs
            r.limit_allocated = sum(allocs.mapped('amount'))
            # Dư nợ phải đếm từ KHẾ ƯỚC, không cộng qua các dòng phân bổ:
            # KW gắn dự án mà facility chưa khai phân bổ cho dự án đó thì
            # cộng theo phân bổ sẽ BỎ SÓT dư nợ, làm ⑧ kê thừa đúng bằng
            # phần sót — đi đàm phán xin hạn mức nhiều hơn thực cần.
            used = 0.0
            if r.project_id:
                notes = self.env['re.loan.note'].search(
                    [('state', 'not in',
                      ('draft', 'cancelled', 'fully_paid'))])
                for n in notes:
                    used += n._outstanding_by_project().get(
                        r.project_id.id, 0.0)
            r.limit_used = used
            r.limit_remaining = max(
                0.0, r.limit_allocated - r.limit_used)
            r.available_now = sum(
                allocs.mapped('amount_available_project'))

    @api.depends('cost_to_complete', 'equity_rate_pct', 'equity_base',
                 'amount_bac', 'equity_in_kind',
                 'equity_contributed', 'supplier_credit', 'supplier_credit_total',
                 'supplier_advance_paid', 'project_id',
                 'limit_remaining')
    def _compute_need(self):
        Contract = self.env['rp.owner.contract']
        for r in self:
            ctc = r.cost_to_complete
            # nhóm 09 Chi phí tài chính + 10 Dự phòng của dự án
            fin = r.amount_finance_contingency
            base = (max(0.0, r.amount_bac - fin)
                    if r.equity_base == 'bac' else ctc)
            r.equity_base_amount = base
            req = base * (r.equity_rate_pct or 0.0) / 100.0
            r.equity_required = req
            contributed = ((r.equity_contributed or 0.0)
                           + (r.equity_in_kind or 0.0))
            r.equity_contributed_total = contributed
            remain = max(0.0, req - contributed)
            r.equity_to_contribute = remain
            r.equity_shortfall = remain
            r.equity_ok = r.equity_shortfall <= 0.01
            adv = 0.0
            if r.project_id:
                # ③ là MẶT TIỀN: tạm ứng CĐT còn TRONG TÀI KHOẢN (chưa
                # dùng trả nhà thầu) — KHÔNG phải "còn phải hoàn CĐT".
                # Anh Đại 2026-08-11: tiền tạm ứng nhận về là nguồn để trả
                # thầu phụ; đã tiêu rồi thì không tài trợ được phần việc
                # còn lại nữa.
                Adv = self.env['rp.owner.advance']
                if 'amount_cash_left' in Adv._fields:
                    adv = sum(Adv.search([
                        ('owner_contract_id.project_id', '=',
                         r.project_id.id),
                        ('state', 'in', ('received', 'closed')),
                    ]).mapped('amount_cash_left'))
                else:
                    adv = sum(Contract.search(
                        [('project_id', '=', r.project_id.id)]
                    ).mapped('advance_balance'))
            r.advance_available = adv
            equity_deduct = remain if r.equity_base == 'bac' else req
            r.funding_need = max(
                0.0, ctc - equity_deduct - adv
                - (r.supplier_credit_total or 0.0)
                - (r.supplier_advance_paid or 0.0))
            r.unfunded_need = max(
                0.0, r.funding_need - r.limit_used)


class ReLoanNoteDisbursementEquityGate(models.Model):
    """CHẶN giải ngân khi dự án góp thiếu vốn tự có (tài liệu nghiệp vụ §3)."""
    _inherit = 're.loan.note.disbursement'

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._check_equity_gate()
        return recs

    def _check_equity_gate(self):
        Funding = self.env['re.loan.project.funding']
        for disb in self:
            proj = disb.note_id.project_id
            if not proj:
                continue
            sheet = Funding.search(
                [('project_id', '=', proj.id)], limit=1)
            if sheet and sheet.equity_shortfall > 0.01:
                raise UserError(_(
                    'Dự án %(p)s đang GÓP THIẾU VỐN TỰ CÓ '
                    '%(m)s (cam kết %(r).0f%% trên CTC = %(req)s, thực góp '
                    '%(c)s) — tạm dừng giải ngân mới cho đến khi bổ sung '
                    '(phiếu Nhu cầu vốn dự án).',
                    p=proj.display_name,
                    m='{:,.0f}'.format(sheet.equity_shortfall),
                    r=sheet.equity_rate_pct,
                    req='{:,.0f}'.format(sheet.equity_required),
                    c='{:,.0f}'.format(sheet.equity_contributed or 0.0)))
