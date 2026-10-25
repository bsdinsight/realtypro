# -*- coding: utf-8 -*-
"""Nối hoá đơn kế toán ngược về kỳ sản lượng đã sinh ra nó.

Vì sao cần: app Kinh doanh phải mở được DANH SÁCH hoá đơn tiền điện mà
không bắt người vận hành sang app Kế toán rồi tự lọc. Muốn lọc thì phải
có dấu vết phân biệt hoá đơn tiền điện với mọi hoá đơn bán khác của
công ty — dấu vết ấy đã có sẵn ở `rp.energy.period.line.invoice_id`,
chỉ là chưa nhìn được từ phía hoá đơn.

KHÔNG thêm cờ boolean "là hoá đơn tiền điện". Cờ là bản sao của sự
thật, mà bản sao thì sẽ lệch: xoá dòng phân bổ đi mà cờ vẫn bật là hoá
đơn nằm lại trong danh sách mãi mãi. Quan hệ ngược không lệch được.
"""
from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    energy_line_ids = fields.One2many(
        'rp.energy.period.line', 'invoice_id',
        string='Dòng sản lượng đã tính tiền')
    energy_period_ids = fields.Many2many(
        'rp.energy.period', string='Kỳ sản lượng',
        compute='_compute_energy', store=True)
    energy_project_id = fields.Many2one(
        're.project', string='Dự án điện',
        compute='_compute_energy', store=True, index=True,
        help='Suy từ dòng sản lượng. Một hoá đơn gộp nhiều kỳ thì các kỳ '
             'ấy đều của cùng một dự án và cùng một bên mua.')
    energy_mwh = fields.Float(
        string='Sản lượng (MWh)', digits=(16, 3),
        compute='_compute_energy', store=True)

    @api.depends('energy_line_ids', 'energy_line_ids.period_id',
                 'energy_line_ids.energy_mwh')
    def _compute_energy(self):
        for mv in self:
            ky = mv.energy_line_ids.mapped('period_id')
            mv.energy_period_ids = [(6, 0, ky.ids)]
            mv.energy_project_id = ky.mapped('project_id')[:1]
            mv.energy_mwh = sum(mv.energy_line_ids.mapped('energy_mwh'))


class AccountPayment(models.Model):
    """Phiếu thu tiền điện.

    Hai chuyện bên mua điện làm suốt, và Odoo vốn đã làm được cả hai —
    việc ở đây chỉ là cho chúng một lối vào và làm chúng NHÌN THẤY được:

    * **Một hoá đơn thu nhiều lần.** Bên mua trả làm vài đợt, hoặc giữ
      lại phần đang đối soát sản lượng. Mỗi lần trả là một phiếu, hoá
      đơn còn số dư cho tới khi trả hết.
    * **Một lần thu nhiều hoá đơn.** EVN chuyển một khoản cho vài tháng,
      hoặc cho vài nhà máy cùng lúc. Một phiếu gánh nhiều tờ.

    Vì cả hai đều có thật nên KHÔNG được suy "một phiếu ↔ một hoá đơn" ở
    bất cứ đâu. `energy_project_id` dưới đây chỉ lấy dự án ĐẦU TIÊN, cốt
    để lọc nhanh ở khung bên trái; muốn biết phiếu gánh những tờ nào thì
    đọc `invoice_ids`, đó mới là sự thật.
    """
    _inherit = 'account.payment'

    energy_invoice_ids = fields.Many2many(
        'account.move', 'rp_payment_energy_invoice_rel',
        'payment_id', 'move_id', string='Trả cho hoá đơn',
        compute='_compute_energy_hd', store=True)
    energy_invoice_count = fields.Integer(
        string='Số hoá đơn', compute='_compute_energy_hd', store=True,
        help='Nhiều hơn 1 là phiếu này trả cho nhiều hoá đơn cùng lúc.')
    energy_project_id = fields.Many2one(
        're.project', string='Dự án điện', compute='_compute_energy_hd',
        store=True, index=True)

    @api.depends('move_id.line_ids.matched_debit_ids',
                 'move_id.line_ids.matched_credit_ids')
    def _compute_energy_hd(self):
        for p in self:
            hd = p._hoa_don_doi_tru().filtered('energy_project_id')
            p.energy_invoice_ids = [(6, 0, hd.ids)]
            p.energy_invoice_count = len(hd)
            p.energy_project_id = hd[:1].energy_project_id

    def _hoa_don_doi_tru(self):
        """Hoá đơn mà phiếu này THỰC SỰ đối trừ.

        KHÔNG dùng `invoice_ids` hay `reconciled_invoice_ids` của Odoo.
        Hai trường ấy đi theo CỤM đối chiếu, nên khi một hoá đơn được
        trả làm hai lần rồi tất toán, mọi phiếu trong cụm đều hiện ra
        mọi hoá đơn trong cụm. Đo trên `aip` ngày 26/10/2026: phiếu
        PBNK1/2026/00027 chỉ trả 60% của một tờ, mà cả hai trường đều
        khai nó trả hai tờ. Cột "Số hoá đơn" dựng trên đó là cột nói
        dối, và nói dối đúng vào chỗ người ta mở màn hình ra để xem.

        Đối trừ TỪNG CẶP thì đúng: mỗi `account.partial.reconcile` nối
        đích danh một dòng của phiếu với một dòng của hoá đơn.
        """
        self.ensure_one()
        hd = self.env['account.move']
        cua_minh = self.move_id.line_ids
        for ln in cua_minh:
            for pr in ln.matched_debit_ids:
                hd |= pr.debit_move_id.move_id
            for pr in ln.matched_credit_ids:
                hd |= pr.credit_move_id.move_id
        return (hd - self.move_id).filtered(lambda m: m.is_invoice())
