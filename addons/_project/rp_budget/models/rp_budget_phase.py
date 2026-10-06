# -*- coding: utf-8 -*-
"""Rải ngân sách theo lịch — đường cong kế hoạch (PV) lấy từ lịch THẬT.

Trước đây PV của dự án bằng 0, nên SPI/SV theo tiền vô nghĩa. Lý do:
PV chỉ tính ở cấp HẠNG MỤC (`estimate_value × đường cong S giả định`),
mà với chủ đầu tư mua trọn gói EPC thì ngân sách nằm ở GÓI THẦU còn
hạng mục để trống — công thức không chạm tới đồng nào.

Cách làm ở đây không giả định hình dạng đường cong. Ngân sách gói thầu
được rải lên chính các CÔNG VIỆC của hợp đồng thuộc gói đó, theo tỷ
trọng thời lượng, rồi mỗi việc rải đều trên số ngày của nó. Hình dạng
đường cong vì vậy là hệ quả của lịch thật — làm nhiều việc tháng nào thì
tháng đó nặng tiền — chứ không phải một chữ S vẽ sẵn.

Hai cái bẫy đã tránh:
 · chỉ lấy việc LÁ (`_rp_viec_la`); cộng cả dòng tổng là ngân sách nhân
   đôi ngay;
 · gói nào không có hợp đồng, hoặc hợp đồng không có việc nào mang
   ngày, thì KHÔNG rải — ghi nhận là "chưa rải được" thay vì bịa một
   đường thẳng, vì bịa xong thì PV trông có vẻ đúng mà sai.
"""
from collections import defaultdict
from datetime import date, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


def _dau_thang(d):
    return date(d.year, d.month, 1)


class RpBudgetPhase(models.Model):
    _name = 'rp.budget.phase'
    _description = 'Ngân sách rải theo tháng'
    _order = 'project_id, period, package_id'

    project_id = fields.Many2one(
        're.project', string='Dự án', required=True, index=True,
        ondelete='cascade')
    package_id = fields.Many2one(
        'rp.tender.package', string='Gói thầu', index=True,
        ondelete='cascade')
    period = fields.Date(
        string='Tháng', required=True, index=True,
        help='Ngày đầu tháng, dùng làm mốc gom nhóm.')
    amount = fields.Monetary(
        string='Ngân sách trong tháng', currency_field='currency_id')
    amount_cumulative = fields.Monetary(
        string='Luỹ kế đến hết tháng', currency_field='currency_id',
        help='Chính là PV cuối tháng đó — đường cong kế hoạch.')
    currency_id = fields.Many2one(
        'res.currency', related='project_id.currency_id',
        store=True, readonly=True)


class ReProjectPhasing(models.Model):
    _inherit = 're.project'

    budget_phase_ids = fields.One2many(
        'rp.budget.phase', 'project_id', string='Ngân sách theo tháng')
    budget_phase_count = fields.Integer(
        string='Số dòng rải', compute='_compute_budget_phase_info')
    budget_phased_total = fields.Monetary(
        string='Đã rải được', compute='_compute_budget_phase_info',
        currency_field='currency_id',
        help='Tổng ngân sách đã rải được lên lịch. Nhỏ hơn ngân sách gốc '
             'nghĩa là có gói chưa có hợp đồng hoặc hợp đồng chưa có '
             'lịch — phần đó không vào PV.')
    budget_unphased_total = fields.Monetary(
        string='Chưa rải được', compute='_compute_budget_phase_info',
        currency_field='currency_id',
        help='Phần ngân sách chưa gắn được vào lịch, ĐÃ TRỪ quỹ dự '
             'phòng. Dự phòng cố ý không rải: nó là khoản để dành, '
             'không phải khối lượng có kế hoạch, nên đưa nó vào đường '
             'cong kế hoạch sẽ làm PV cao giả và SPI đẹp giả.')

    @api.depends('budget_phase_ids.amount', 'total_bac',
                 'contingency_budget')
    def _compute_budget_phase_info(self):
        for proj in self:
            da_rai = sum(proj.budget_phase_ids.mapped('amount'))
            proj.budget_phase_count = len(proj.budget_phase_ids)
            proj.budget_phased_total = da_rai
            proj.budget_unphased_total = ((proj.total_bac or 0.0) - da_rai
                                          - (proj.contingency_budget or 0.0))

    # ------------------------------------------------------------------
    # Rải
    # ------------------------------------------------------------------
    def _rp_lat_cat_theo_lich(self):
        """Trả về [(ngày_bắt_đầu, ngày_kết_thúc, tiền, gói)] của từng việc.

        Mỗi phần tử là một lát ngân sách gắn vào một khoảng thời gian
        thật trên lịch.
        """
        self.ensure_one()
        Task = self.env['project.task']
        Contract = self.env['rp.contract']
        lat = []
        chua_rai = []
        goi_co_ns = self.env['rp.tender.package'].search(
            [('project_id', '=', self.id)]).filtered(
                lambda g: g.budget_amount)
        for goi in goi_co_ns:
            hd = Contract.search([('tender_package_id', '=', goi.id)])
            viec = Task.search([('rp_contract_id', 'in', hd.ids)]) \
                if hd else Task
            la = [t for t in Task._rp_viec_la(viec)
                  if t.planned_start and t.planned_end
                  and t.planned_end >= t.planned_start]
            tong_ngay = sum(
                (t.planned_end - t.planned_start).days + 1 for t in la)
            if not tong_ngay:
                chua_rai.append(goi)
                continue
            for t in la:
                so_ngay = (t.planned_end - t.planned_start).days + 1
                lat.append((t.planned_start, t.planned_end,
                            goi.budget_amount * so_ngay / tong_ngay, goi))
        return lat, chua_rai

    def _rp_pv_den_ngay(self, moc=None):
        """PV(t) — tiền kế hoạch phải làm ra tính đến ngày `moc`."""
        self.ensure_one()
        moc = moc or fields.Date.context_today(self)
        lat, _chua = self._rp_lat_cat_theo_lich()
        pv = 0.0
        for bd, kt, tien, _goi in lat:
            if moc >= kt:
                pv += tien
            elif moc >= bd:
                tong = (kt - bd).days + 1
                da_qua = (moc - bd).days + 1
                pv += tien * da_qua / tong
        return pv

    def action_rai_ngan_sach_theo_lich(self):
        """Dựng lại bảng ngân sách theo tháng từ lịch hiện tại."""
        self.ensure_one()
        lat, chua_rai = self._rp_lat_cat_theo_lich()
        if not lat:
            raise UserError(_(
                "Không rải được: chưa gói thầu nào vừa có ngân sách vừa "
                "có hợp đồng mang lịch công việc.\n\nRải ngân sách cần "
                "ngày bắt đầu/kết thúc kế hoạch trên công việc của hợp "
                "đồng thuộc gói."))
        theo_thang = defaultdict(float)
        for bd, kt, tien, goi in lat:
            tong_ngay = (kt - bd).days + 1
            moi_ngay = tien / tong_ngay
            d = bd
            while d <= kt:
                theo_thang[(goi.id, _dau_thang(d))] += moi_ngay
                d += timedelta(days=1)

        self.budget_phase_ids.unlink()
        Phase = self.env['rp.budget.phase']
        luy_ke = defaultdict(float)
        # Luỹ kế phải cộng theo THỨ TỰ THỜI GIAN của từng gói, nên sắp
        # theo (gói, tháng) trước khi tạo.
        for (goi_id, thang) in sorted(theo_thang,
                                      key=lambda k: (k[0], k[1])):
            tien = theo_thang[(goi_id, thang)]
            luy_ke[goi_id] += tien
            Phase.create({
                'project_id': self.id, 'package_id': goi_id,
                'period': thang, 'amount': tien,
                'amount_cumulative': luy_ke[goi_id],
            })
        msg = _('Đã rải %(so)s dòng tháng từ lịch.', so=len(theo_thang))
        if chua_rai:
            msg += _('\nChưa rải được (thiếu hợp đồng hoặc thiếu lịch): '
                     '%s.', ', '.join(chua_rai.mapped('code')))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'warning' if chua_rai else 'success',
                'title': _('Rải ngân sách theo lịch'),
                'message': msg,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def _compute_project_schedule(self):
        """Cộng thêm PV từ ngân sách GÓI THẦU rải theo lịch.

        Bản gốc ở rp_evm chỉ cộng PV của hạng mục, nên dự án EPC mua
        trọn gói có PV = 0 và SPI/SV theo tiền vô nghĩa. Ở đây tính lại
        đủ, và loại hạng mục đã nằm trong gói CÓ ngân sách đúng như cách
        BAC làm — nếu không là đếm đúp.
        """
        super()._compute_project_schedule()
        Package = self.env['rp.tender.package']
        for proj in self:
            goi_co_ns = (Package.search([('project_id', '=', proj.id)])
                         if proj.id else Package).filtered(
                lambda g: g.budget_amount)
            if not goi_co_ns:
                continue
            da_tinh = goi_co_ns.mapped('line_ids.structure_id')
            pv = (sum((proj.structure_ids - da_tinh).mapped(
                      'planned_value_today'))
                  + proj._rp_pv_den_ngay())
            ev = sum(proj.structure_ids.mapped('progress_value'))
            proj.total_pv_today = pv
            proj.total_sv = ev - pv
            proj.project_spi = (ev / pv) if pv else 0.0

    def action_mo_rai_ngan_sach(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ngân sách theo tháng — %s', self.name),
            'res_model': 'rp.budget.phase',
            'view_mode': 'list',
            'domain': [('project_id', '=', self.id)],
            'context': {'search_default_group_period': 1},
        }
