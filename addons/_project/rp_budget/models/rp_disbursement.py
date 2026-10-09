# -*- coding: utf-8 -*-
"""Kế hoạch dòng tiền ra và đối chiếu với thực tế giải ngân.

Ba đường cong, đừng lẫn vào nhau
--------------------------------
Dự án xây dựng có BA đường tiền theo thời gian, và chúng không trùng nhau:

* **Ngân sách theo lịch** (``rp.budget.phase``) — khối lượng công việc quy
  ra tiền, rải theo ngày làm việc thật. Đây là PV của EVM: *tháng này
  đáng ra làm ra bao nhiêu tiền giá trị*.
* **Kế hoạch giải ngân** (bảng này, cột kế hoạch) — tiền RỜI KHỎI TÚI
  theo điều khoản thanh toán của hợp đồng: tạm ứng, các đợt theo nghiệm
  thu, giữ lại bảo hành. Luôn lệch pha với đường trên, vì tạm ứng trả
  trước khi có khối lượng còn phần giữ lại trả sau khi xong rất lâu.
* **Thực tế giải ngân** (cột thực tế) — tiền đã thật sự chi.

Lấy đường ngân sách làm kế hoạch dòng tiền là sai lệch có hệ thống: nó
bỏ qua tạm ứng (chi sớm) lẫn tiền giữ lại (chi muộn). Nên bảng này dựng
kế hoạch từ **đợt thanh toán của hợp đồng**, là nơi điều khoản tiền thật
sự nằm.

Số thực tế dùng lại ĐÚNG định nghĩa mà hệ thống đã dùng cho
``rp.contract.amount_paid`` — đợt ở trạng thái "Đã trả" — chứ không tự
định nghĩa lần thứ hai. Hai định nghĩa "đã thanh toán" trong cùng một hệ
thống thì sớm muộn cũng ra hai con số khác nhau trên hai màn hình, và
không ai biết tin cái nào.
"""
from collections import defaultdict
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError


def _dau_thang(d):
    return date(d.year, d.month, 1)


class RpDisbursementLine(models.Model):
    _name = 'rp.disbursement.line'
    _description = 'Giải ngân theo tháng — kế hoạch so thực tế'
    _order = 'project_id, period, package_id'

    project_id = fields.Many2one(
        're.project', string='Dự án', required=True, index=True,
        ondelete='cascade')
    package_id = fields.Many2one(
        'rp.tender.package', string='Gói thầu', index=True,
        ondelete='cascade')
    contract_id = fields.Many2one(
        'rp.contract', string='Hợp đồng', index=True, ondelete='cascade')
    # Lưu theo THÁNG, nhưng là trường Date nên gom nhóm trên giao diện
    # vẫn cuộn lên được tuần / quý / năm mà không phải khai thêm trường
    # nào. Người test hỏi "theo tuần/tháng/năm" — chỗ đó là nút Nhóm
    # theo, không phải ba bảng khác nhau.
    period = fields.Date(
        string='Tháng', required=True, index=True,
        help='Ngày đầu tháng. Trên danh sách và pivot có thể gom theo '
             'tuần, quý hay năm bằng "Nhóm theo".')

    amount_plan = fields.Monetary(
        string='Kế hoạch chi', currency_field='currency_id',
        help='Theo điều khoản thanh toán của hợp đồng: tạm ứng và các '
             'đợt, lấy theo NGÀY ĐẾN HẠN.')
    amount_actual = fields.Monetary(
        string='Thực chi', currency_field='currency_id',
        help='Đợt đã ở trạng thái "Đã trả" và tạm ứng đã chi, lấy theo '
             'NGÀY TRẢ thật.')
    amount_plan_cum = fields.Monetary(
        string='Kế hoạch luỹ kế', currency_field='currency_id')
    amount_actual_cum = fields.Monetary(
        string='Thực chi luỹ kế', currency_field='currency_id')

    variance = fields.Monetary(
        string='Sai lệch', compute='_compute_variance', store=True,
        currency_field='currency_id',
        help='Thực chi − Kế hoạch. ÂM nghĩa là chi chậm hơn kế hoạch: '
             'nhẹ gánh tiền trước mắt, nhưng thường là dấu hiệu công '
             'việc chậm hoặc hồ sơ nghiệm thu đang tắc.')
    variance_cum = fields.Monetary(
        string='Sai lệch luỹ kế', compute='_compute_variance', store=True,
        currency_field='currency_id')
    variance_percent = fields.Float(
        string='Sai lệch (%)', compute='_compute_variance', store=True,
        digits=(6, 1), aggregator=False)

    status = fields.Selection(
        [('future', 'Chưa tới hạn'),
         ('on_track', 'Đúng kế hoạch'),
         ('under', 'Chi chậm'),
         ('over', 'Chi vượt')],
        string='Tình trạng', compute='_compute_variance', store=True)

    currency_id = fields.Many2one(
        'res.currency', related='project_id.currency_id',
        store=True, readonly=True)

    _uniq_dong = models.Constraint(
        'UNIQUE(project_id, package_id, contract_id, period)',
        'Mỗi hợp đồng chỉ có một dòng cho mỗi tháng.')

    @api.depends('amount_plan', 'amount_actual',
                 'amount_plan_cum', 'amount_actual_cum', 'period')
    def _compute_variance(self):
        hn = fields.Date.context_today(self)
        for d in self:
            d.variance = (d.amount_actual or 0.0) - (d.amount_plan or 0.0)
            d.variance_cum = ((d.amount_actual_cum or 0.0)
                              - (d.amount_plan_cum or 0.0))
            d.variance_percent = (
                d.variance / d.amount_plan * 100.0 if d.amount_plan else 0.0)
            # Tháng chưa tới thì không có "chậm" — chưa đến hạn mà đã
            # tô đỏ thì cả bảng đỏ rực và không ai nhìn nữa.
            if d.period and d.period > _dau_thang(hn):
                d.status = 'future'
            elif abs(d.variance) <= max(1.0, (d.amount_plan or 0.0) * 0.02):
                d.status = 'on_track'
            elif d.variance < 0:
                d.status = 'under'
            else:
                d.status = 'over'

    @api.depends('project_id', 'package_id', 'period')
    def _compute_display_name(self):
        for d in self:
            d.display_name = '%s · %s' % (
                d.package_id.code or d.project_id.name or '',
                d.period.strftime('%m/%Y') if d.period else '')


class ReProjectDisbursement(models.Model):
    _inherit = 're.project'

    disbursement_line_ids = fields.One2many(
        'rp.disbursement.line', 'project_id', string='Giải ngân theo tháng')
    disbursement_line_count = fields.Integer(
        string='Số dòng giải ngân', compute='_compute_disbursement',
        store=True)
    disbursement_plan_total = fields.Monetary(
        string='Tổng kế hoạch chi', compute='_compute_disbursement',
        store=True, currency_field='currency_id')
    disbursement_actual_total = fields.Monetary(
        string='Tổng đã chi', compute='_compute_disbursement',
        store=True, currency_field='currency_id')
    disbursement_overdue_total = fields.Monetary(
        string='Quá hạn chưa chi', compute='_compute_disbursement',
        store=True, currency_field='currency_id',
        help='Phần kế hoạch của các tháng ĐÃ QUA mà chưa chi ra. Đây là '
             'chỗ hoặc công việc đang chậm, hoặc hồ sơ thanh toán đang '
             'tắc ở đâu đó.')

    @api.depends('disbursement_line_ids.amount_plan',
                 'disbursement_line_ids.amount_actual',
                 'disbursement_line_ids.status')
    def _compute_disbursement(self):
        hn = fields.Date.context_today(self)
        dau = _dau_thang(hn)
        for p in self:
            d = p.disbursement_line_ids
            p.disbursement_line_count = len(d)
            p.disbursement_plan_total = sum(d.mapped('amount_plan'))
            p.disbursement_actual_total = sum(d.mapped('amount_actual'))
            qua = d.filtered(lambda x: x.period and x.period < dau)
            p.disbursement_overdue_total = max(
                sum(qua.mapped('amount_plan'))
                - sum(qua.mapped('amount_actual')), 0.0)

    # ------------------------------------------------------------------
    # Dựng bảng
    # ------------------------------------------------------------------
    def _rp_lat_giai_ngan(self):
        """Gom các lát tiền thành {(gói, hợp đồng, tháng): [kế hoạch, thực]}.

        Nguồn:
        * Đợt thanh toán của hợp đồng — ``due_date`` cho kế hoạch,
          ``paid_date`` cho thực tế.
        * Tạm ứng — ``date_request`` (hoặc ngày duyệt) cho kế hoạch,
          ``date_paid`` cho thực tế.

        Đợt đã trả mà KHÔNG có ngày trả thì rơi về ngày đến hạn, kèm
        đếm riêng để báo ra: bỏ qua nó thì tổng thực chi hụt một cách
        âm thầm, còn tính vào tháng hiện tại thì làm méo đường cong.
        """
        self.ensure_one()
        Contract = self.env['rp.contract']
        hd = Contract.search([('project_id', '=', self.id)])
        o = defaultdict(lambda: [0.0, 0.0])
        thieu_ngay = 0

        for c in hd:
            khoa = (c.tender_package_id.id or False, c.id)
            for m in c.payment_milestone_ids:
                if m.due_date:
                    o[khoa + (_dau_thang(m.due_date),)][0] += m.amount or 0.0
                if m.state == 'paid':
                    ng = m.paid_date or m.due_date
                    if not m.paid_date:
                        thieu_ngay += 1
                    if ng:
                        o[khoa + (_dau_thang(ng),)][1] += m.amount or 0.0

        Advance = self.env.get('rp.advance.payment')
        if Advance is not None:
            for a in Advance.sudo().search([('contract_id', 'in', hd.ids)]):
                c = a.contract_id
                khoa = (c.tender_package_id.id or False, c.id)
                kh = a.date_approval or a.date_request
                if kh:
                    o[khoa + (_dau_thang(kh),)][0] += a.amount or 0.0
                if a.date_paid and a.amount_paid:
                    o[khoa + (_dau_thang(a.date_paid),)][1] += a.amount_paid
        return o, thieu_ngay

    def action_dung_bang_giai_ngan(self):
        """Dựng lại bảng giải ngân từ điều khoản thanh toán hiện tại."""
        self.ensure_one()
        o, thieu_ngay = self._rp_lat_giai_ngan()
        if not o:
            raise UserError(_(
                'Chưa dựng được: không hợp đồng nào của dự án có đợt '
                'thanh toán hay tạm ứng.\n\nKế hoạch giải ngân lấy từ '
                'ĐIỀU KHOẢN THANH TOÁN của hợp đồng — khai các đợt trên '
                'hợp đồng trước, rồi dựng lại.'))

        self.disbursement_line_ids.unlink()
        Line = self.env['rp.disbursement.line']
        luy = defaultdict(lambda: [0.0, 0.0])
        rows = []
        # Luỹ kế cộng theo thứ tự thời gian TRONG TỪNG hợp đồng.
        for (goi, hop_dong, thang) in sorted(o, key=lambda k: (k[1], k[2])):
            kh, tt = o[(goi, hop_dong, thang)]
            luy[hop_dong][0] += kh
            luy[hop_dong][1] += tt
            rows.append({
                'project_id': self.id,
                'package_id': goi or False,
                'contract_id': hop_dong,
                'period': thang,
                'amount_plan': kh,
                'amount_actual': tt,
                'amount_plan_cum': luy[hop_dong][0],
                'amount_actual_cum': luy[hop_dong][1],
            })
        Line.create(rows)

        msg = _('Đã dựng %(n)s dòng tháng từ điều khoản thanh toán.',
                n=len(rows))
        if thieu_ngay:
            msg += _('\n\n%(k)s đợt đã đánh dấu "Đã trả" nhưng KHÔNG có '
                     'ngày trả — tạm xếp vào tháng đến hạn. Bổ sung ngày '
                     'trả để đường cong thực tế đúng chỗ.', k=thieu_ngay)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': _('Giải ngân'), 'message': msg,
                       'type': 'warning' if thieu_ngay else 'success',
                       'sticky': bool(thieu_ngay)},
        }

    def action_mo_giai_ngan(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Giải ngân — %s', self.name),
            'res_model': 'rp.disbursement.line',
            'view_mode': 'list,pivot,graph',
            'domain': [('project_id', '=', self.id)],
            'context': {'search_default_g_goi': 1},
        }


class RpTenderPackageDisbursement(models.Model):
    _inherit = 'rp.tender.package'

    disbursement_line_ids = fields.One2many(
        'rp.disbursement.line', 'package_id', string='Giải ngân theo tháng')
    disbursement_plan_total = fields.Monetary(
        string='Kế hoạch chi', compute='_compute_disbursement',
        currency_field='currency_id')
    disbursement_actual_total = fields.Monetary(
        string='Đã chi', compute='_compute_disbursement',
        currency_field='currency_id')
    disbursement_percent = fields.Float(
        string='Đã chi / kế hoạch (%)', compute='_compute_disbursement',
        digits=(6, 1), aggregator=False)

    @api.depends('disbursement_line_ids.amount_plan',
                 'disbursement_line_ids.amount_actual')
    def _compute_disbursement(self):
        for g in self:
            d = g.disbursement_line_ids
            kh = sum(d.mapped('amount_plan'))
            tt = sum(d.mapped('amount_actual'))
            g.disbursement_plan_total = kh
            g.disbursement_actual_total = tt
            g.disbursement_percent = tt * 100.0 / kh if kh else 0.0

    def action_mo_giai_ngan(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Giải ngân — %s', self.display_name),
            'res_model': 'rp.disbursement.line',
            'view_mode': 'list,pivot,graph',
            'domain': [('package_id', '=', self.id)],
        }
