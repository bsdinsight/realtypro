# -*- coding: utf-8 -*-
"""Gom chi phí thực và tiền đã ra về GÓI THẦU — trục mà ngân sách dùng.

Chi phí thực (AC) hiện roll-up theo HẠNG MỤC: dòng hoá đơn mang
`structure_id`, cộng lên `rp.structure.actual_cost`. Với chủ đầu tư mua
trọn gói EPC thì ngân sách nằm ở GÓI THẦU còn hạng mục để trống, nên
bảng ngân sách có ngân sách một bên, chi phí một bên, KHÔNG cộng khớp
nhau — đúng căn bệnh đã giết PV trước đây.

May là chuỗi liên kết đã có sẵn, không phải dựng mới:

    hoá đơn → mốc thanh toán → hợp đồng → gói thầu
    (`account.move.payment_milestone_id`)

nên chỉ cần đi ngược chuỗi đó để gom về gói. Hoá đơn mua thẳng không
qua mốc thanh toán sẽ không có gói — đúng, vì nó không thuộc gói nào.

Hai cột tiền KHÔNG được gộp, vì chúng nằm trên hai cơ sở khác nhau:
 · **Chi phí thực (AC)** — cơ sở dồn tích, từ hoá đơn đã vào sổ;
 · **Tiền đã ra** — cơ sở tiền, gồm cả tạm ứng.
Tạm ứng là trả trước (331), KHÔNG phải chi phí. Gộp vào AC thì CPI méo
ngay đầu dự án: ứng trước 15% mà chưa làm gì, CPI sẽ về gần 0 và báo
cáo nói dự án đã vỡ trong khi nó mới chỉ ứng tiền.
"""
from odoo import api, fields, models


class RpTenderPackageCost(models.Model):
    _inherit = 'rp.tender.package'

    cost_invoiced = fields.Monetary(
        string='Đã có hoá đơn', compute='_compute_chi_phi_goi',
        currency_field='currency_id',
        help='Σ giá trị chưa thuế của hoá đơn nhà thầu ĐÃ VÀO SỔ thuộc '
             'các hợp đồng của gói. Hoá đơn điều chỉnh giảm trừ ra.')
    cost_paid = fields.Monetary(
        string='Đã thanh toán hoá đơn', compute='_compute_chi_phi_goi',
        currency_field='currency_id')
    cost_advance = fields.Monetary(
        string='Đã tạm ứng', compute='_compute_chi_phi_goi',
        currency_field='currency_id',
        help='Tiền đã ứng trước cho nhà thầu. Là TIỀN ĐÃ RA chứ không '
             'phải chi phí — nó nằm ở tài khoản trả trước người bán cho '
             'tới khi được cấn trừ vào hoá đơn.')
    value_accepted = fields.Monetary(
        string='Đã nghiệm thu', compute='_compute_chi_phi_goi',
        currency_field='currency_id',
        help='Σ giá trị biên bản nghiệm thu ĐÃ DUYỆT — chính là EV của gói.')
    cost_remaining = fields.Monetary(
        string='Còn phải chi', compute='_compute_chi_phi_goi',
        currency_field='currency_id',
        help='Ngân sách gói trừ phần đã có hoá đơn.')

    def _rp_hoa_don_cua_goi(self):
        """Hoá đơn nhà thầu đi theo chuỗi mốc thanh toán về gói này."""
        self.ensure_one()
        Move = self.env['account.move']
        if 'payment_milestone_id' not in Move._fields or not self.id:
            return Move
        return Move.search([
            ('move_type', 'in', ('in_invoice', 'in_refund')),
            ('state', '=', 'posted'),
            ('payment_milestone_id.contract_id.tender_package_id',
             '=', self.id),
        ])

    @api.depends('budget_amount')
    def _compute_chi_phi_goi(self):
        Contract = self.env['rp.contract']
        Acc = self.env['rp.progress.acceptance']
        Advance = self.env.get('rp.advance.payment')
        for goi in self:
            hoa_don = goi._rp_hoa_don_cua_goi()
            da_hd = 0.0
            da_tra = 0.0
            for m in hoa_don:
                dau = -1.0 if m.move_type == 'in_refund' else 1.0
                da_hd += dau * (m.amount_untaxed or 0.0)
                da_tra += dau * ((m.amount_total or 0.0)
                                 - (m.amount_residual or 0.0))
            hd = Contract.search(
                [('tender_package_id', '=', goi.id)]) if goi.id else Contract
            nt = Acc.search([('contract_id', 'in', hd.ids),
                             ('state', '=', 'approved')]) if hd else Acc
            ung = 0.0
            if Advance is not None and hd:
                ung = sum(Advance.search(
                    [('contract_id', 'in', hd.ids)]).mapped('amount_paid'))
            goi.cost_invoiced = da_hd
            goi.cost_paid = da_tra
            goi.cost_advance = ung
            goi.value_accepted = sum(nt.mapped('total_value_period'))
            goi.cost_remaining = (goi.budget_amount or 0.0) - da_hd


class ReProjectCost(models.Model):
    _inherit = 're.project'

    cost_invoiced_total = fields.Monetary(
        string='Đã có hoá đơn', compute='_compute_chi_phi_du_an',
        currency_field='currency_id')
    cost_paid_total = fields.Monetary(
        string='Đã thanh toán hoá đơn', compute='_compute_chi_phi_du_an',
        currency_field='currency_id')
    cost_advance_total = fields.Monetary(
        string='Đã tạm ứng', compute='_compute_chi_phi_du_an',
        currency_field='currency_id')
    cash_out_total = fields.Monetary(
        string='Tổng tiền đã ra', compute='_compute_chi_phi_du_an',
        currency_field='currency_id',
        help='Tạm ứng + thanh toán hoá đơn. Cơ sở TIỀN, khác hẳn chi phí '
             'thực (cơ sở dồn tích) — hai con số này lệch nhau rất xa ở '
             'giai đoạn đầu dự án và không được gộp.')

    @api.depends('total_bac')
    def _compute_chi_phi_du_an(self):
        Package = self.env['rp.tender.package']
        for proj in self:
            goi = Package.search(
                [('project_id', '=', proj.id)]) if proj.id else Package
            proj.cost_invoiced_total = sum(goi.mapped('cost_invoiced'))
            proj.cost_paid_total = sum(goi.mapped('cost_paid'))
            proj.cost_advance_total = sum(goi.mapped('cost_advance'))
            proj.cash_out_total = (proj.cost_paid_total
                                   + proj.cost_advance_total)

    def _compute_project_evm(self):
        """Cộng chi phí thực của GÓI THẦU vào AC của dự án.

        Bản gốc chỉ cộng `rp.structure.actual_cost`, tức chỉ thấy hoá
        đơn có gắn hạng mục. Hoá đơn của gói thầu EPC không gắn hạng mục
        nào nên AC = 0 và CPI chết — cùng kiểu với PV trước đây.
        """
        super()._compute_project_evm()
        Package = self.env['rp.tender.package']
        for proj in self:
            goi = Package.search(
                [('project_id', '=', proj.id)]) if proj.id else Package
            them = sum(goi.mapped('cost_invoiced'))
            if not them:
                continue
            ac = (proj.total_ac or 0.0) + them
            proj.total_ac = ac
            proj.total_cv = (proj.total_ev or 0.0) - ac
            cpi = ((proj.total_ev or 0.0) / ac) if ac else 0.0
            proj.project_cpi = cpi
            proj.project_eac = ((proj.total_bac or 0.0) / cpi) if cpi \
                else (proj.total_bac or 0.0)
            proj.project_vac = (proj.total_bac or 0.0) - proj.project_eac
