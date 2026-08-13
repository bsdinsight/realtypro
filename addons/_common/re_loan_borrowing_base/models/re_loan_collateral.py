# -*- coding: utf-8 -*-
"""TSBĐ Quyền đòi nợ — collateral gắn HĐ với CĐT, giá trị tự động.

Advance rate mặc định khai trên loại TSBĐ (re.loan.collateral.type).
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ReLoanCollateralType(models.Model):
    _inherit = 're.loan.collateral.type'

    advance_rate = fields.Float(
        string='Tỷ lệ cho vay (%)', default=0.0,
        help='Tỷ lệ NH cho vay trên giá trị TSBĐ loại này (BĐS ~70, '
             'quyền đòi nợ ~50-70, tiền gửi ~95). Mặc định cho pledge — '
             'override được từng pledge. 0 = chưa khai → KHÔNG tính '
             'vào borrowing base.')


class ReLoanCollateral(models.Model):
    _inherit = 're.loan.collateral'

    owner_contract_id = fields.Many2one(
        'rp.owner.contract', string='HĐ với CĐT (quyền đòi nợ)',
        ondelete='restrict', index=True,
        help='Gắn HĐ đầu ra với Chủ đầu tư → tài sản này là QUYỀN ĐÒI '
             'NỢ: giá trị tự cập nhật = khoản phải thu (sản lượng CĐT '
             'duyệt − CĐT đã trả, floor 0). Mỗi biến động tự sinh bản '
             'ghi định giá (audit).')

    owner_ipc_id = fields.Many2one(
        'rp.owner.ipc', string='IPC (CĐT đã ký)',
        ondelete='restrict', index=True,
        help='Gắn MỘT IPC đã được CĐT ký nhận → tài sản này là quyền đòi '
             'nợ của riêng IPC đó, giá trị = quyền đòi nợ trên IPC. '
             'Chi tiết hơn cấp HĐ và là chứng từ NH muốn thấy.')

    def write(self, vals):
        res = super().write(vals)
        if 'owner_contract_id' in vals or 'owner_ipc_id' in vals:
            self.filtered(
                lambda c: c.owner_contract_id or c.owner_ipc_id
            )._sync_receivable_valuation(reason=_('Gắn nguồn quyền đòi nợ'))
        return res

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs.filtered(
            lambda c: c.owner_contract_id or c.owner_ipc_id
        )._sync_receivable_valuation(reason=_('Gắn nguồn quyền đòi nợ'))
        return recs

    @api.constrains('owner_contract_id', 'owner_ipc_id')
    def _check_receivable_source(self):
        for rec in self:
            if rec.owner_contract_id and rec.owner_ipc_id:
                raise ValidationError(_(
                    'TSBĐ "%s" gắn CẢ hợp đồng CĐT lẫn IPC — chọn MỘT '
                    'cấp thôi, gắn cả hai là thế chấp trùng.', rec.name))
            if rec.owner_ipc_id and rec.owner_ipc_id.state != 'signed':
                raise ValidationError(_(
                    'IPC %s chưa được CĐT ký nhận — chưa đủ điều kiện '
                    'làm TSBĐ.', rec.owner_ipc_id.name))

    def _sync_receivable_valuation(self, reason=''):
        """Tạo bản ghi định giá = khoản phải thu hiện hành (floor 0).

        HAI CẤP, loại trừ nhau:
        - cấp IPC  → giá trị = quyền đòi nợ của IPC đó, TRỪ phần chủ đầu
                     tư đã trả cho chính IPC đó (đối soát ngân hàng);
        - cấp HĐ   → giá trị = phải thu CHƯA cầm cố theo IPC
                     (`receivable_unpledged`), để không thế chấp trùng.

        VÌ SAO TRỪ PHẦN ĐÃ THU: tiền đã về tài khoản thì không còn là
        khoản phải thu nữa — không thể đem thế chấp một khoản mình đã
        được trả. Giữ nguyên giá trị sau khi thu làm borrowing base cao
        hơn thực tế, tức hệ thống báo còn dư địa vay trong khi tài sản
        bảo đảm đã tiêu biến. Đây là sai về phía nguy hiểm (rút vượt),
        nên trừ ngay tại nguồn định giá.

        CHỈ trừ ở CẤP IPC, cố ý. Cấp hợp đồng lấy `receivable_unpledged`
        = phải thu − Σ phần đã cầm cố; nếu trừ tiếp ở đó nữa thì một
        khoản thu bị trừ HAI LẦN và borrowing base tụt sai chiều ngược.

        Bỏ qua nếu giá trị không đổi so với định giá mới nhất (tránh
        spam record khi không có biến động thực).
        """
        Valuation = self.env['re.loan.collateral.valuation']
        today = fields.Date.context_today(self)
        for col in self:
            if col.owner_ipc_id:
                ipc = col.owner_ipc_id
                got = ipc.amount_received or 0.0
                value = max(0.0, (ipc.amount_certified or 0.0) - got)
                detail = _(
                    'IPC %(i)s (CĐT ký %(d)s, VB %(r)s): quyền đòi nợ '
                    '%(q)s − CĐT đã trả %(g)s = %(v)s.',
                    i=ipc.name, d=ipc.date_signed or '—',
                    r=ipc.sign_ref or '—',
                    q='{:,.0f}'.format(ipc.amount_certified or 0.0),
                    g='{:,.0f}'.format(got),
                    v='{:,.0f}'.format(value))
            elif col.owner_contract_id:
                value = max(0.0, col.owner_contract_id.receivable_unpledged)
                detail = _(
                    'phải thu HĐ %(c)s = nghiệm thu %(a)s − đã trả %(p)s '
                    '− đã cầm cố theo IPC %(x)s.',
                    c=col.owner_contract_id.name,
                    a='{:,.0f}'.format(
                        col.owner_contract_id.accepted_to_date),
                    p='{:,.0f}'.format(
                        col.owner_contract_id.paid_to_date),
                    x='{:,.0f}'.format(
                        col.owner_contract_id.receivable_pledged_ipc))
            else:
                continue
            # Key an toàn với record chưa lưu (NewId) + date trống —
            # cùng convention với _compute_value_current (re_loan).
            date_min = fields.Date.to_date('1900-01-01')
            latest = col.valuation_ids.sorted(
                key=lambda v: (v.date or date_min,
                               v.id if isinstance(v.id, int)
                               else float('inf')),
                reverse=True)[:1]
            if latest and abs(latest.amount - value) < 0.01:
                continue
            Valuation.create({
                'collateral_id': col.id,
                'date': today,
                'amount': value,
                'method': 'cost',
                'appraiser': _('Tự động theo sản lượng/thanh toán'),
                'note': _('Auto (%(r)s): %(d)s',
                          r=reason or _('biến động'), d=detail),
            })


class ReLoanCollateralProjectAxis(models.Model):
    """Trục DỰ ÁN cho TSBĐ — nguyên tắc nghiệp vụ: quyền đòi nợ của dự án X chỉ
    bảo đảm cho khoản vay của dự án X, không tự động gánh dự án khác.
    TSBĐ không gắn dự án (BĐS, tiền gửi...) = TSBĐ CHUNG, gánh cả gói."""
    _inherit = 're.loan.collateral'

    project_id = fields.Many2one(
        're.project', string='Dự án (ring-fence)',
        compute='_compute_project_id', store=True, index=True,
        help='TSBĐ quyền đòi nợ thuộc dự án nào — tự lấy từ IPC/HĐ CĐT. '
             'TRỐNG = tài sản chung của doanh nghiệp, bảo đảm chung cho '
             'toàn bộ gói tín dụng (bể dùng chung).')

    @api.depends('owner_ipc_id.project_id', 'owner_contract_id.project_id')
    def _compute_project_id(self):
        for rec in self:
            rec.project_id = (rec.owner_ipc_id.project_id
                              or rec.owner_contract_id.project_id)
