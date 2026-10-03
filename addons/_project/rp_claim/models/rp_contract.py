# -*- coding: utf-8 -*-
"""Phạt chậm tiến độ, tính trên mốc hoàn thành ĐÃ GIA HẠN.

Đây là chỗ hai sổ phải gặp nhau. Phạt chậm luôn được tính từ "ngày hoàn
thành theo hợp đồng", mà ngày đó dời mỗi lần có khiếu nại gia hạn được
chấp thuận. Nếu phần mềm tính phạt theo ngày ký ban đầu thì con số lúc
nào cũng sai và không ai dám dùng.

Số ngày chậm ở đây lấy từ LỊCH THI CÔNG (ngày về đích dự báo của chính
hợp đồng), nên nó là con số dự báo — dùng để cảnh báo sớm và để đàm
phán. Khi cần chốt chính thức thì lập biên bản (rp.ld.assessment), lúc
đó số liệu được đóng băng kèm ngày chốt.
"""
from odoo import _, api, fields, models


class RpContract(models.Model):
    _inherit = 'rp.contract'

    claim_ids = fields.One2many(
        'rp.claim', 'contract_id', string='Khiếu nại')
    claim_count = fields.Integer(
        string='Số khiếu nại', compute='_compute_claim_stats')
    claim_open_count = fields.Integer(
        string='Khiếu nại đang mở', compute='_compute_claim_stats')
    eot_days_granted = fields.Integer(
        string='Tổng ngày đã gia hạn', compute='_compute_claim_stats',
        store=True,
        help='Cộng dồn số ngày gia hạn của các khiếu nại đã được chấp '
             'thuận. Đây là căn cứ dời mốc tính phạt chậm.')
    date_completion_adjusted = fields.Date(
        string='Hoàn thành theo HĐ (đã gia hạn)',
        compute='_compute_claim_stats', store=True)

    # --- Cấu hình phạt chậm ----------------------------------------
    ld_rate_per_day = fields.Float(
        string='Mức phạt (%/ngày)', digits=(5, 4), default=0.05,
        help='Phần trăm giá trị phần hợp đồng bị vi phạm, tính cho mỗi '
             'ngày chậm. Lấy đúng theo điều khoản phạt của hợp đồng.')
    ld_cap_percent = fields.Float(
        string='Trần phạt (%)', digits=(5, 2), default=12.0,
        help='Mức phạt tối đa theo hợp đồng. Với công trình dùng vốn nhà '
             'nước, pháp luật xây dựng Việt Nam giới hạn 12% giá trị phần '
             'hợp đồng bị vi phạm; hợp đồng khác do hai bên thoả thuận — '
             'hãy điền đúng con số ghi trong hợp đồng.')
    ld_base_amount = fields.Monetary(
        string='Giá trị làm căn cứ phạt',
        compute='_compute_ld', store=True, readonly=False,
        help='Mặc định là giá trị hợp đồng trước thuế. Nếu hợp đồng chỉ '
             'phạt trên phần việc bị chậm thì sửa lại con số này.')
    ld_forecast_end = fields.Date(
        string='Về đích dự báo (theo lịch)', compute='_compute_ld',
        store=True)
    ld_days_late = fields.Integer(
        string='Số ngày chậm dự kiến', compute='_compute_ld', store=True)
    ld_amount_exposure = fields.Monetary(
        string='Tiền phạt dự kiến', compute='_compute_ld', store=True,
        help='Số ngày chậm × mức phạt × giá trị căn cứ, đã áp trần. Là '
             'con số DỰ BÁO theo lịch hiện hành, chưa phải quyết định.')
    ld_capped = fields.Boolean(
        string='Đã chạm trần', compute='_compute_ld', store=True)
    ld_assessment_ids = fields.One2many(
        'rp.ld.assessment', 'contract_id', string='Biên bản tính phạt')
    ld_assessment_count = fields.Integer(
        string='Số biên bản phạt', compute='_compute_claim_stats')

    @api.depends('claim_ids.state', 'claim_ids.eot_days_granted',
                 'date_end', 'ld_assessment_ids')
    def _compute_claim_stats(self):
        for rec in self:
            claims = rec.claim_ids
            rec.claim_count = len(claims)
            rec.claim_open_count = len(claims.filtered(
                lambda c: c.state not in ('rejected', 'closed')))
            granted = sum(claims.filtered(
                lambda c: c.state in ('agreed', 'partial')).mapped(
                    'eot_days_granted'))
            rec.eot_days_granted = granted
            rec.date_completion_adjusted = (
                fields.Date.add(rec.date_end, days=granted)
                if rec.date_end else False)
            rec.ld_assessment_count = len(rec.ld_assessment_ids)

    # task_ids.planned_end: thiếu phụ thuộc này thì tiền phạt đứng yên
    # trong khi lịch đã đổi — con số sai mà không ai biết.
    @api.depends('date_completion_adjusted', 'contract_value_pretax',
                 'ld_rate_per_day', 'ld_cap_percent',
                 'task_ids.planned_end')
    def _compute_ld(self):
        for rec in self:
            if not rec.ld_base_amount:
                rec.ld_base_amount = rec.contract_value_pretax
            ends = [t.planned_end for t in rec.task_ids if t.planned_end]
            rec.ld_forecast_end = max(ends) if ends else False
            due = rec.date_completion_adjusted
            late = ((rec.ld_forecast_end - due).days
                    if (rec.ld_forecast_end and due) else 0)
            rec.ld_days_late = max(late, 0)
            raw = (rec.ld_base_amount * (rec.ld_rate_per_day / 100.0)
                   * rec.ld_days_late)
            cap = rec.ld_base_amount * (rec.ld_cap_percent / 100.0)
            rec.ld_amount_exposure = min(raw, cap) if rec.ld_days_late else 0
            rec.ld_capped = bool(rec.ld_days_late) and raw > cap

    # ------------------------------------------------------------------
    def action_open_claims(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Khiếu nại — %s', self.name),
            'res_model': 'rp.claim',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id},
        }

    def action_open_ld_assessments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Biên bản tính phạt — %s', self.name),
            'res_model': 'rp.ld.assessment',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id},
        }

    def action_create_ld_assessment(self):
        """Đóng băng số liệu phạt tại thời điểm chốt."""
        self.ensure_one()
        am = self.env['rp.ld.assessment'].create({
            'contract_id': self.id,
            'date_cutoff': fields.Date.context_today(self),
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'rp.ld.assessment',
            'res_id': am.id,
            'views': [[False, 'form']],
        }
