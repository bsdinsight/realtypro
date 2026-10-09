# -*- coding: utf-8 -*-
"""Cảnh báo thiếu tiền: sắp phải chi bao nhiêu, còn rút được bao nhiêu.

Đây là câu hỏi của giám đốc tài chính chứ không phải của kế toán: *ba
tháng tới dự án phải chi ra bao nhiêu, và nguồn còn rút được có đủ
không*. Trả lời được câu đó thì xoay tiền còn kịp; trả lời muộn thì
thành chậm thanh toán, nhà thầu dừng việc, và kéo theo cả tiến độ.

Phạm vi của con số — nói trước để không ai đọc nhầm
---------------------------------------------------
"Nguồn còn rút được" ở đây CHỈ tính hạn mức tín dụng còn khả dụng đã
phân bổ cho dự án. Nó **không** tính vốn chủ sở hữu sẽ góp, tiền mặt
đang có, hay dòng tiền vào từ bán hàng / bán điện. Vì vậy đây là chỉ
báo **khoảng hở tài trợ**, không phải dự báo ngân quỹ.

Nói rõ phạm vi quan trọng hơn là làm con số trông toàn diện: một số
"dòng tiền" gộp cả những nguồn chưa chắc chắn sẽ luôn đẹp hơn thực tế,
và người đọc sẽ yên tâm nhầm đúng vào lúc không nên yên tâm.
"""
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ReProjectCashAlert(models.Model):
    _inherit = 're.project'

    cash_horizon_months = fields.Integer(
        string='Tầm nhìn tiền (tháng)', default=3,
        help='Nhìn trước bao nhiêu tháng để so nhu cầu chi với nguồn còn '
             'rút được. Ba tháng là khoảng vừa đủ để kịp xoay một khoản '
             'giải ngân mới.')
    cash_need = fields.Monetary(
        string='Cần chi trong tầm nhìn', compute='_compute_cash',
        currency_field='currency_id',
        help='Kế hoạch chi của các tháng tới, CỘNG phần đã quá hạn mà '
             'chưa chi — khoản quá hạn vẫn phải trả, và thường phải trả '
             'ngay.')
    cash_overdue = fields.Monetary(
        string='Trong đó: đã quá hạn', compute='_compute_cash',
        currency_field='currency_id')
    cash_available = fields.Monetary(
        string='Nguồn còn rút được', compute='_compute_cash',
        currency_field='currency_id',
        help='CHỈ gồm hạn mức tín dụng còn khả dụng đã phân bổ cho dự '
             'án này. Không gồm vốn chủ, tiền mặt đang có, hay tiền thu '
             'về. Đây là khoảng hở tài trợ, không phải dự báo ngân quỹ.')
    cash_gap = fields.Monetary(
        string='Thiếu', compute='_compute_cash',
        currency_field='currency_id',
        help='Cần chi − nguồn còn rút được. Lớn hơn 0 là phải xoay thêm '
             'tiền từ nguồn khác.')
    # Lưu lại để LỌC được "dự án đang thiếu tiền" ngay trên danh sách —
    # trường tính không lưu thì không đưa vào domain được. Cái giá của
    # việc lưu: nó phụ thuộc NGÀY HÔM NAY mà ngày thì tự trôi, nên phải
    # có cron đánh thức. Đã dính đúng bẫy này ở bộ đếm ngày bảo lãnh,
    # nơi con số đứng im suốt và không ai nhận ra.
    cash_alert = fields.Boolean(
        string='Cảnh báo thiếu tiền', compute='_compute_cash',
        store=True, index=True)

    @api.depends('disbursement_line_ids.amount_plan',
                 'disbursement_line_ids.amount_actual',
                 'disbursement_line_ids.period', 'cash_horizon_months')
    def _compute_cash(self):
        hn = fields.Date.context_today(self)
        for p in self:
            den = hn + relativedelta(months=p.cash_horizon_months or 3)
            qua, toi = 0.0, 0.0
            for d in p.disbursement_line_ids:
                if not d.period:
                    continue
                con_lai = max((d.amount_plan or 0.0)
                              - (d.amount_actual or 0.0), 0.0)
                if d.period < hn.replace(day=1):
                    qua += con_lai
                elif d.period <= den:
                    toi += con_lai
            p.cash_overdue = qua
            p.cash_need = qua + toi
            p.cash_available = p._rp_nguon_con_rut()
            p.cash_gap = max(p.cash_need - p.cash_available, 0.0)
            p.cash_alert = p.cash_gap > 0

    def _rp_nguon_con_rut(self):
        """Hạn mức tín dụng còn khả dụng đã phân bổ cho dự án này.

        Hai đường gắn hạn mức với dự án, và phải xử cả hai nhưng KHÔNG
        được cộng đúp:

        * hạn mức khai thẳng ``project_id`` — dùng trọn cho dự án;
        * hạn mức dùng chung, phân bổ từng phần qua bảng phân bổ.

        Với hạn mức dùng chung thì phần khả dụng của dự án bị chặn trên
        bởi CẢ phần được phân bổ LẪN phần cả hạn mức còn lại — ngân hàng
        không cho rút quá cái nào trong hai.

        Bẫy cộng đúp: hạn mức bật cờ **liên thông** thì
        ``amount_available`` của nó trả về phần còn lại của CẢ BỂ dùng
        chung, không phải của riêng nó. Cộng thẳng mấy hạn mức cùng bể
        là nhân số tiền lên đúng bằng số hạn mức trong bể — và nhân lên
        theo hướng làm cảnh báo IM LẶNG, tức hỏng đúng lúc cần nhất.
        """
        self.ensure_one()
        F = self.env.get('re.loan.facility')
        if F is None:
            return 0.0
        rieng = F.sudo().search([('project_id', '=', self.id)])
        # Hạn mức không liên thông: cộng bình thường.
        tong = sum(max(f.amount_available or 0.0, 0.0)
                   for f in rieng.filtered(lambda x: not x.flexible_limits))
        # Hạn mức liên thông: mỗi BỂ (theo hợp đồng tín dụng) chỉ đếm
        # một lần.
        be = {}
        for f in rieng.filtered('flexible_limits'):
            be[f.credit_contract_id.id] = max(f.amount_available or 0.0, 0.0)
        tong += sum(be.values())

        A = self.env.get('re.loan.facility.project.allocation')
        if A is not None:
            da_tinh = set(rieng.ids)
            for a in A.sudo().search([('project_id', '=', self.id),
                                      ('facility_id', 'not in', rieng.ids)]):
                f = a.facility_id
                # Một hạn mức có thể có NHIỀU dòng phân bổ cho cùng dự
                # án (demo AMI đang có đúng thế). Cộng từng dòng là cộng
                # đúp phần khả dụng của chính hạn mức đó.
                if f.id in da_tinh:
                    continue
                da_tinh.add(f.id)
                phan_bo = sum(A.sudo().search([
                    ('project_id', '=', self.id),
                    ('facility_id', '=', f.id)]).mapped('amount'))
                tong += max(min(phan_bo, f.amount_available or 0.0), 0.0)
        return tong

    @api.model
    def _cron_canh_bao_thieu_tien(self):
        """Tính lại cảnh báo mỗi ngày.

        ``cash_alert`` được lưu nên lọc được, nhưng nó phụ thuộc ngày
        hôm nay: một tháng kế hoạch hôm qua còn "sắp tới" thì hôm nay đã
        thành "quá hạn". Không đánh thức thì cờ đứng im ở giá trị của
        ngày nó được tính lần cuối — im lặng và sai.
        """
        du_an = self.search([('disbursement_line_ids', '!=', False)])
        du_an._compute_cash()
        du_an.flush_recordset(['cash_alert'])
        return True

    def action_mo_nguon_von(self):
        self.ensure_one()
        if 're.loan.facility' not in self.env:
            raise UserError(_(
                'Phân hệ Quản lý Vay chưa được cài, nên chưa có hạn mức '
                'tín dụng nào để xem.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Hạn mức tín dụng — %s', self.name),
            'res_model': 're.loan.facility',
            'view_mode': 'list,form',
            'domain': ['|', ('project_id', '=', self.id),
                       ('project_allocation_ids.project_id', '=', self.id)],
        }
