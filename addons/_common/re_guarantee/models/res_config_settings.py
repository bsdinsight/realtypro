# -*- coding: utf-8 -*-
"""Cấu hình phân hệ Bảo lãnh.

Hai nhóm tham số:

1. NHẮC BẢO LÃNH SẮP HẾT HẠN (backlog 760) — vốn chỉ nằm ở Cấu hình >
   Kỹ thuật > Tham số hệ thống, chỗ mà người theo dõi bảo lãnh không có
   quyền vào, và cũng không ai nghĩ tới khi đi tìm "cấu hình nhắc trước
   bao nhiêu ngày". Đưa lên màn hình cấu hình của phân hệ.

2. TÀI KHOẢN KẾ TOÁN CHO CÁC ĐỢT THANH TOÁN BL (backlog 969) — mỗi lần
   trả tiền cho ngân hàng theo chứng thư nay sinh một PHIẾU CHI thật
   (account.payment) thay vì chỉ ghi vào bảng riêng. Đối ứng của phiếu
   chi phụ thuộc BẢN CHẤT khoản trả, nên phải khai rõ từng loại — team
   khách hàng chốt 2026-09-11:

     Phí BL        → 642  Chi phí quản lý doanh nghiệp
     Phạt quá hạn  → 811  Chi phí khác
     Ký quỹ        → 244  Cầm cố, thế chấp, ký quỹ, ký cược  (TÀI SẢN,
                          không phải chi phí — NH trả lại khi giải toả)
     Tiền gốc      → 3411 Các khoản đi vay (NH đã trả thay cho
                          beneficiary, doanh nghiệp hoàn lại)

   Bốn tài khoản này KHÔNG suy ra được từ dữ liệu, và đoán sai thì sổ
   cái sai im lặng — nên để trống là chặn, không có mặc định ngầm.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

DEFAULT_LEAD_DAYS = 30
DEFAULT_REPEAT_DAYS = 7

# payment_kind trên re.bank.guarantee.payment → tên trường cấu hình.
GUARANTEE_KIND_ACCOUNT_FIELDS = {
    'fee': 're_guarantee_fee_account_id',
    'penalty': 're_guarantee_penalty_account_id',
    'deposit': 're_guarantee_deposit_account_id',
    'principal': 're_guarantee_principal_account_id',
}


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    re_guarantee_expiry_lead_days = fields.Integer(
        string='Nhắc trước (ngày)',
        config_parameter='re_guarantee.expiry_lead_days',
        default=DEFAULT_LEAD_DAYS,
        help='Bắt đầu gửi thư nhắc khi chứng thư còn bao nhiêu ngày là '
             'hết hạn. Để 0 thì dùng mặc định %s ngày.'
             % DEFAULT_LEAD_DAYS)
    re_guarantee_expiry_repeat_days = fields.Integer(
        string='Nhắc lặp lại sau (ngày)',
        config_parameter='re_guarantee.expiry_repeat_days',
        default=DEFAULT_REPEAT_DAYS,
        help='Đã nhắc rồi thì bao nhiêu ngày sau nhắc lại, chừng nào '
             'chứng thư chưa được xử lý. Để 0 thì dùng mặc định %s '
             'ngày.' % DEFAULT_REPEAT_DAYS)

    @api.constrains('re_guarantee_expiry_lead_days',
                    're_guarantee_expiry_repeat_days')
    def _check_expiry_days(self):
        for wiz in self:
            if wiz.re_guarantee_expiry_lead_days < 0 \
                    or wiz.re_guarantee_expiry_repeat_days < 0:
                raise ValidationError(_(
                    'Số ngày nhắc không được âm.'))
            if wiz.re_guarantee_expiry_lead_days > 365:
                raise ValidationError(_(
                    'Nhắc trước quá 365 ngày thì thư nhắc mất ý nghĩa — '
                    'chứng thư nào cũng "sắp hết hạn".'))

    # ------------------------------------------------------------------
    # Kế toán thanh toán bảo lãnh (backlog 969)
    # ------------------------------------------------------------------
    re_guarantee_journal_id = fields.Many2one(
        'account.journal', string='Sổ nhật ký chi (BL)',
        domain="[('type', 'in', ('bank', 'cash'))]",
        config_parameter='re_guarantee.payment_journal_id',
        help='Sổ nhật ký dùng khi sinh phiếu chi cho các đợt thanh '
             'toán chứng thư BL. Nếu đợt thanh toán có khai "Tài '
             'khoản chuyển tiền" thì hệ thống ưu tiên sổ của đúng tài '
             'khoản đó; ô này là mức dự phòng.')
    re_guarantee_fee_account_id = fields.Many2one(
        'account.account', string='TK chi phí — Phí BL',
        config_parameter='re_guarantee.fee_account_id',
        help='Đối ứng phiếu chi khi trả phí bảo lãnh (642).')
    re_guarantee_penalty_account_id = fields.Many2one(
        'account.account', string='TK chi phí — Phạt quá hạn',
        config_parameter='re_guarantee.penalty_account_id',
        help='Đối ứng phiếu chi khi trả phạt quá hạn (811).')
    re_guarantee_deposit_account_id = fields.Many2one(
        'account.account', string='TK ký quỹ',
        config_parameter='re_guarantee.deposit_account_id',
        help='Đối ứng phiếu chi khi nộp ký quỹ, và đối ứng phiếu thu '
             'khi ngân hàng hoàn ký quỹ lúc giải toả BL (244). Đây là '
             'TÀI SẢN, không phải chi phí.')
    re_guarantee_principal_account_id = fields.Many2one(
        'account.account', string='TK hoàn gốc BL bị thu',
        config_parameter='re_guarantee.principal_account_id',
        help='Đối ứng phiếu chi khi hoàn lại ngân hàng số tiền NH đã '
             'trả thay cho beneficiary (3411).')

    @api.model
    def _guarantee_payment_account(self, payment_kind):
        """TK đối ứng đã cấu hình cho một loại thanh toán BL."""
        fname = GUARANTEE_KIND_ACCOUNT_FIELDS.get(payment_kind)
        if not fname:
            return self.env['account.account']
        param = self._fields[fname].config_parameter
        raw = self.env['ir.config_parameter'].sudo().get_param(param)
        try:
            account = self.env['account.account'].browse(int(raw or 0))
        except (TypeError, ValueError):
            return self.env['account.account']
        return account.exists()

    @api.model
    def _guarantee_payment_journal(self):
        raw = self.env['ir.config_parameter'].sudo().get_param(
            're_guarantee.payment_journal_id')
        try:
            journal = self.env['account.journal'].browse(int(raw or 0))
        except (TypeError, ValueError):
            return self.env['account.journal']
        return journal.exists()

    @api.model
    def _require_guarantee_account(self, payment_kind, label):
        account = self._guarantee_payment_account(payment_kind)
        if not account:
            raise UserError(_(
                "Chưa khai tài khoản kế toán cho khoản \"%(k)s\".\n"
                "Vào Vay > Cấu hình > Tham số phân hệ Vay, mục "
                "\"Kế toán thanh toán bảo lãnh\" để khai — không có "
                "tài khoản thì phiếu chi hạch toán vào đâu cũng sai.",
                k=label))
        return account
