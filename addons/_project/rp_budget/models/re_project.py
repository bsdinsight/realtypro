# -*- coding: utf-8 -*-
"""Ba lớp ngân sách trên dự án.

    Gốc      = mốc đã chốt (số đóng băng)
    Hiện hành = gốc + phát sinh ĐÃ DUYỆT
    Dự báo    = cost_forecast_total của sổ phát sinh (đã gồm cam kết hợp
                đồng + phát sinh đã duyệt chưa vào hợp đồng + đang chờ)

Dự báo KHÔNG tính lại ở đây. Sổ phát sinh đã tính rồi, và phát sinh có
thể mang số ÂM (khoản cắt bớt khối lượng), nên tự cộng lại là chắc chắn
lệch.

Tất cả để non-stored vì `variation_approved_total` và
`cost_forecast_total` bên sổ phát sinh cũng non-stored — khai store ở
đây sẽ ra số cũ mà không ai biết.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ReProject(models.Model):
    _inherit = 're.project'

    cost_baseline_ids = fields.One2many(
        'rp.cost.baseline', 'project_id', string='Mốc ngân sách')
    cost_baseline_id = fields.Many2one(
        'rp.cost.baseline', string='Mốc đang hiệu lực',
        compute='_compute_ngan_sach_3_lop')
    cost_baseline_count = fields.Integer(
        string='Số mốc ngân sách', compute='_compute_ngan_sach_3_lop')

    budget_original = fields.Monetary(
        string='① Ngân sách gốc', compute='_compute_ngan_sach_3_lop',
        currency_field='currency_id',
        help='Số đã chốt ở mốc đang hiệu lực. Chưa chốt mốc nào thì bằng 0.')
    budget_current = fields.Monetary(
        string='② Ngân sách hiện hành', compute='_compute_ngan_sach_3_lop',
        currency_field='currency_id',
        help='Gốc + phát sinh đã duyệt. Đây là số tiền được phép tiêu '
             'tại thời điểm này.')
    budget_forecast = fields.Monetary(
        string='③ Dự báo cuối kỳ', compute='_compute_ngan_sach_3_lop',
        currency_field='currency_id',
        help='Đã cam kết theo hợp đồng + phát sinh đã duyệt chưa vào hợp '
             'đồng + phát sinh đang chờ.')
    budget_revision_total = fields.Monetary(
        string='Đã điều chỉnh (②−①)', compute='_compute_ngan_sach_3_lop',
        currency_field='currency_id',
        help='Ngân sách đã được nới thêm bao nhiêu so với lúc phê duyệt.')
    budget_forecast_gap = fields.Monetary(
        string='Dự kiến vượt (③−②)', compute='_compute_ngan_sach_3_lop',
        currency_field='currency_id',
        help='Dương là dự báo tiêu quá số được phép tiêu. Đây mới là con '
             'số cần nhìn, không phải chênh so với ngân sách gốc.')
    budget_drift = fields.Monetary(
        string='Độ trôi ngân sách', compute='_compute_ngan_sach_3_lop',
        currency_field='currency_id',
        help='BAC tính động trừ ngân sách gốc. Khác 0 nghĩa là có người '
             'sửa BOQ/dự toán sau khi đã chốt mốc mà không qua phát sinh '
             '— ngân sách đang trôi âm thầm.')
    budget_status = fields.Selection(
        [('no_baseline', 'Chưa chốt mốc'),
         ('on_budget', 'Trong ngân sách'),
         ('using_contingency', 'Đang tiêu dự phòng'),
         ('drifted', 'Ngân sách đã trôi'),
         ('over', 'Dự kiến vượt')],
        string='Tình trạng ngân sách', compute='_compute_ngan_sach_3_lop')

    # ----- Quỹ dự phòng
    contingency_drawdown_ids = fields.One2many(
        'rp.contingency.drawdown', 'project_id', string='Phiếu rút dự phòng')
    contingency_drawdown_count = fields.Integer(
        string='Số phiếu rút', compute='_compute_du_phong')
    contingency_budget = fields.Monetary(
        string='Quỹ dự phòng', compute='_compute_du_phong',
        currency_field='currency_id',
        help='Phần dự phòng đã chụp trong mốc đang hiệu lực. Nằm TRONG '
             'ngân sách gốc, không cộng thêm.')
    contingency_used = fields.Monetary(
        string='Đã rút dự phòng', compute='_compute_du_phong',
        currency_field='currency_id')
    contingency_remaining = fields.Monetary(
        string='Dự phòng còn lại', compute='_compute_du_phong',
        currency_field='currency_id')
    contingency_used_pct = fields.Float(
        string='% dự phòng đã dùng', compute='_compute_du_phong',
        digits=(16, 1),
        help='Thang 0–100. Tiêu hết phần lớn dự phòng khi khối lượng mới '
             'làm được ít là dấu hiệu hỏng sớm, dù báo cáo vẫn nói "trong '
             'ngân sách".')

    @api.depends('contingency_drawdown_ids.state',
                 'contingency_drawdown_ids.amount',
                 'cost_baseline_ids.state',
                 'cost_baseline_ids.contingency_amount')
    def _compute_du_phong(self):
        for proj in self:
            moc = proj.cost_baseline_ids.filtered(
                lambda b: b.state == 'active')[:1]
            quy = moc.contingency_amount if moc else 0.0
            da_rut = sum(proj.contingency_drawdown_ids.filtered(
                lambda d: d.state == 'confirmed').mapped('amount'))
            proj.contingency_budget = quy
            proj.contingency_used = da_rut
            proj.contingency_remaining = quy - da_rut
            proj.contingency_used_pct = (da_rut / quy * 100.0) if quy else 0.0
            proj.contingency_drawdown_count = len(
                proj.contingency_drawdown_ids)

    @api.depends('cost_baseline_ids.state', 'cost_baseline_ids.amount_total',
                 'total_bac', 'variation_approved_total',
                 'cost_forecast_total',
                 'contingency_drawdown_ids.state',
                 'contingency_drawdown_ids.amount')
    def _compute_ngan_sach_3_lop(self):
        for proj in self:
            moc = proj.cost_baseline_ids.filtered(
                lambda b: b.state == 'active')[:1]
            goc = moc.amount_total if moc else 0.0
            # Phát sinh được tài trợ bằng dự phòng thì KHÔNG nới tổng:
            # tiền chuyển từ dòng dự phòng sang phần việc, tổng y nguyên.
            # Trừ đi phần đã rút chính là chỗ cài luật đó.
            hien_hanh = (goc + (proj.variation_approved_total or 0.0)
                         - (proj.contingency_used or 0.0))
            du_bao = proj.cost_forecast_total or 0.0
            troi = (proj.total_bac or 0.0) - goc if moc else 0.0

            proj.cost_baseline_id = moc
            proj.cost_baseline_count = len(proj.cost_baseline_ids)
            proj.budget_original = goc
            proj.budget_current = hien_hanh
            proj.budget_forecast = du_bao
            proj.budget_revision_total = hien_hanh - goc
            proj.budget_forecast_gap = du_bao - hien_hanh
            proj.budget_drift = troi

            if not moc:
                proj.budget_status = 'no_baseline'
            elif du_bao - hien_hanh > 0:
                proj.budget_status = 'over'
            elif abs(troi) > 0.01:
                # Trôi mà chưa vượt vẫn phải báo: nó nghĩa là ngân sách
                # đang bị sửa ngoài luồng phát sinh.
                proj.budget_status = 'drifted'
            elif proj.contingency_used > 0:
                # Chưa vượt, nhưng đang ăn vào quỹ — nói thẳng ra thay vì
                # để nó lẫn vào "trong ngân sách".
                proj.budget_status = 'using_contingency'
            else:
                proj.budget_status = 'on_budget'

    def action_chot_ngan_sach_goc(self):
        """Chụp BAC hiện tại thành một mốc mới và đưa vào hiệu lực."""
        self.ensure_one()
        dong = self._bac_breakdown()
        if not dong:
            raise UserError(_(
                "Dự án chưa có khoản ngân sách nào để chốt. Khai ngân "
                "sách cho gói thầu (BOQ) hoặc dự toán hạng mục trước."))
        cu = self.env['rp.cost.baseline'].search(
            [('project_id', '=', self.id)], order='revision desc', limit=1)
        lan = (cu.revision + 1) if cu else 0
        moc = self.env['rp.cost.baseline'].create({
            'project_id': self.id,
            'name': _('Ngân sách gốc') if not lan
                    else _('Ngân sách chốt lại lần %s', lan),
            'revision': lan,
            'amount_total': sum(d['amount'] for d in dong),
            'contingency_amount': sum(d['amount'] for d in dong
                                      if d.get('is_contingency')),
            'line_ids': [(0, 0, d) for d in dong],
        })
        moc.action_kich_hoat()
        moc.message_post(body=_(
            'Chốt mốc ngân sách: %(tien)s trên %(so)s khoản.',
            tien=moc.amount_total, so=len(dong)))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Mốc ngân sách'),
            'res_model': 'rp.cost.baseline',
            'res_id': moc.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_mo_moc_ngan_sach(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Mốc ngân sách — %s', self.name),
            'res_model': 'rp.cost.baseline',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_mo_so_rut_du_phong(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sổ rút dự phòng — %s', self.name),
            'res_model': 'rp.contingency.drawdown',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }
