# -*- coding: utf-8 -*-
"""Sổ đệm giao dịch ngân hàng — nguồn-bất-khả-tri.

Vì sao có tầng đệm thay vì cho webhook ghi thẳng vào IPC/khế ước:
- **Chống trùng + phát lại**: webhook có thể bắn lại → `external_id` làm khoá
  idempotent (dùng `id`/`referenceCode` của SePay).
- **Nguồn thay được**: SePay hôm nay, Casso/API ngân hàng/sao kê ngày mai —
  chỉ viết adapter mới, tầng đối soát không đổi (`source`).
- **Sai thì sửa được**: khớp nhầm thì gỡ khớp, không phải sửa chứng từ thật.

Đối soát vào IPC/đặt cọc/trả nợ để ở module bridge riêng — model này KHÔNG
biết IPC là gì (giữ _common tái dùng được cho mọi chứng từ).
"""
from odoo import _, api, fields, models


class ReBankTransaction(models.Model):
    _name = 're.bank.transaction'
    _description = 'Giao dịch ngân hàng (sổ đệm đối soát)'
    _inherit = ['mail.thread']
    _order = 'txn_date desc, id desc'

    name = fields.Char(compute='_compute_name', store=True)
    source = fields.Selection([
        ('sepay', 'SePay (webhook)'),
        ('file_import', 'Nhập từ file (sao kê)'),
        ('ai_advice', 'AI đọc chứng từ'),
        ('manual', 'Nhập tay'),
    ], string='Nguồn', required=True, default='manual', index=True,
        tracking=True)

    bank_gateway = fields.Char(string='Ngân hàng', help='VD: MBBank, VCB')
    account_number = fields.Char(string='Số tài khoản')
    txn_date = fields.Datetime(string='Thời điểm', index=True)
    direction = fields.Selection([
        ('in', 'Tiền vào'),
        ('out', 'Tiền ra'),
    ], string='Chiều', required=True, default='in', index=True)
    amount = fields.Monetary(string='Số tiền', required=True)
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda s: s.env.company.currency_id)

    content = fields.Char(string='Nội dung', help='Nội dung chuyển khoản')
    code = fields.Char(string='Mã tham chiếu (code)', index=True,
                       help='Mã thanh toán SePay tách được từ nội dung CK.')
    reference_code = fields.Char(string='Mã giao dịch NH (FT)')
    accumulated = fields.Monetary(string='Số dư luỹ kế')

    external_id = fields.Char(
        string='ID nguồn (chống trùng)', index=True, copy=False,
        help='ID giao dịch từ nguồn (SePay payload id). Khoá idempotent — '
             'cùng nguồn + cùng ID = cùng một giao dịch, không tạo lại.')
    raw_payload = fields.Text(string='Payload gốc', copy=False)

    state = fields.Selection([
        ('new', 'Mới nhận'),
        ('matched', 'Đã khớp'),
        ('reconciled', 'Đã đối soát'),
        ('ignored', 'Bỏ qua'),
    ], string='Trạng thái', default='new', required=True, index=True,
        tracking=True)

    # chứng từ đã đối soát vào (IPC / đặt cọc / trả nợ...) — tham chiếu mềm
    matched_ref = fields.Reference(
        selection='_selection_matched_ref', string='Đối soát vào',
        help='Chứng từ mà giao dịch này được đối soát vào.')
    matched_note = fields.Char(string='Ghi chú khớp')

    company_id = fields.Many2one(
        'res.company', default=lambda s: s.env.company, index=True)

    _uniq_source_ext = models.Constraint(
        'unique(source, external_id)',
        'Giao dịch này đã có (trùng nguồn + ID nguồn).')

    @api.model
    def _selection_matched_ref(self):
        # module bridge (vd rp_owner_contract) mở rộng danh sách này
        return [('re.bank.transaction', '—')]

    @api.depends('direction', 'amount', 'content', 'txn_date')
    def _compute_name(self):
        for r in self:
            sign = '+' if r.direction == 'in' else '−'
            amt = '{:,.0f}'.format(r.amount or 0)
            r.name = '%s%s · %s' % (sign, amt, (r.content or '')[:40])

    # ------------------------------------------------------------------
    @api.model
    def ingest(self, vals):
        """Tạo giao dịch từ một nguồn, chống trùng theo (source, external_id).

        Trả về (record, created:bool). Nguồn nào cũng gọi qua đây — webhook
        SePay, import file, AI — để dedup tập trung.
        """
        source = vals.get('source', 'manual')
        ext = vals.get('external_id')
        if ext:
            existing = self.search([
                ('source', '=', source), ('external_id', '=', ext)], limit=1)
            if existing:
                return existing, False
        rec = self.create(vals)
        rec._try_auto_match()
        return rec, True

    def _try_auto_match(self):
        """Hook đối soát tự động — module bridge override.

        Ở _common không biết IPC/đặt cọc là gì nên để trống; bridge (vd
        rp_owner_contract) sẽ khớp theo `code`/`content`.
        """
        return

    def action_ignore(self):
        self.write({'state': 'ignored'})

    def action_reset_new(self):
        self.write({'state': 'new', 'matched_ref': False,
                    'matched_note': False})
