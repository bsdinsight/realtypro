# -*- coding: utf-8 -*-
"""EVM rollup cấp dự án — tổng BAC/EV/AC + CPI/EAC/VAC + đếm hạng mục vượt chi."""
from odoo import api, fields, models

CPI_OVER = 0.90


class ReProject(models.Model):
    _inherit = 're.project'

    currency_id = fields.Many2one(
        'res.currency', string='Loại tiền',
        compute='_compute_currency_id', store=True, readonly=True)
    total_bac = fields.Monetary(
        string='Tổng ngân sách (BAC)', compute='_compute_project_evm',
        store=True, currency_field='currency_id')
    total_ev = fields.Monetary(
        string='Tổng giá trị làm ra (EV)', compute='_compute_project_evm',
        store=True, currency_field='currency_id')
    total_ac = fields.Monetary(
        string='Tổng chi phí thực (AC)', compute='_compute_project_evm',
        store=True, currency_field='currency_id')
    total_cv = fields.Monetary(
        string='Chênh chi phí (CV)', compute='_compute_project_evm',
        store=True, currency_field='currency_id')
    project_cpi = fields.Float(
        string='CPI dự án', compute='_compute_project_evm', store=True,
        digits=(16, 2))
    project_eac = fields.Monetary(
        string='Dự báo chi cuối (EAC)', compute='_compute_project_evm',
        store=True, currency_field='currency_id')
    project_vac = fields.Monetary(
        string='Chênh khi hoàn thành (VAC)', compute='_compute_project_evm',
        store=True, currency_field='currency_id')
    over_budget_count = fields.Integer(
        string='Số hạng mục vượt chi', compute='_compute_project_evm',
        store=True)
    cost_status = fields.Selection(
        [('no_data', 'Chưa đủ dữ liệu'),
         ('on_budget', 'Trong ngân sách'),
         ('watch', 'Cần theo dõi'),
         ('over', 'Vượt chi')],
        string='Trạng thái chi phí dự án',
        compute='_compute_project_evm', store=True, default='no_data')

    # --- Phase 4: schedule performance (non-stored, đổi theo ngày) ---
    total_pv_today = fields.Monetary(
        string='Giá trị kế hoạch đến nay — PV(t)',
        compute='_compute_project_schedule', currency_field='currency_id')
    total_sv = fields.Monetary(
        string='Chênh tiến độ (SV)',
        compute='_compute_project_schedule', currency_field='currency_id')
    project_spi = fields.Float(
        string='SPI dự án', compute='_compute_project_schedule',
        digits=(16, 2))

    def _compute_project_schedule(self):
        for proj in self:
            pv = sum(proj.structure_ids.mapped('planned_value_today'))
            ev = sum(proj.structure_ids.mapped('progress_value'))
            proj.total_pv_today = pv
            proj.total_sv = ev - pv
            proj.project_spi = (ev / pv) if pv else 0.0

    def _compute_currency_id(self):
        default = self.env.company.currency_id
        for proj in self:
            proj.currency_id = proj.currency_id or default

    def _bac_breakdown(self):
        """Các dòng cấu thành BAC, mỗi dòng một khoản ngân sách.

        BAC = Σ ngân sách GÓI THẦU + Σ dự toán HẠNG MỤC chưa nằm trong
        gói nào có ngân sách + chi phí CẤP DỰ ÁN (quản lý dự án, lán
        trại, bảo hiểm… — không thuộc hạng mục nào). Anh Đại chốt
        2026-08-10: thiếu phần cấp dự án thì CTC và Nhu cầu vốn tính hụt
        đúng bằng nó (tài liệu nghiệp vụ §3 đòi chi phí ĐỦ đến hoàn
        thành).

        Ngân sách lấy ở cấp mà chủ đầu tư KÝ được hợp đồng và ĐO được
        tiền ra:
         · mua trọn gói EPC → ngân sách nằm ở GÓI THẦU (BOQ của chủ đầu
           tư), vì nhà thầu không báo tiền theo hạng mục;
         · tự làm, đo khối lượng → ngân sách nằm ở HẠNG MỤC.
        Cộng cả hai, nhưng hạng mục đã nằm trong một gói CÓ ngân sách
        thì không cộng lại — nếu không là đếm đúp.

        Trả về danh sách dict thay vì một con số, để chỗ khác (rp_budget
        chốt mốc ngân sách gốc) cộng ĐÚNG cách này. Hai nơi tự cộng lấy
        là kiểu gì cũng có ngày ra hai con số khác nhau mà không ai biết
        bên nào đúng.
        """
        self.ensure_one()
        Package = self.env['rp.tender.package']
        goi = Package.search([('project_id', '=', self.id)]) \
            if self.id else Package
        goi_co_ns = goi.filtered(lambda p: p.budget_amount)
        da_tinh = goi_co_ns.mapped('line_ids.structure_id')
        dong = []
        for p in goi_co_ns:
            dong.append({
                'source': 'package', 'package_id': p.id,
                'ref_code': p.code or '', 'ref_name': p.name or '',
                'amount': p.budget_amount,
            })
        for s in (self.structure_ids - da_tinh):
            if not s.estimate_value:
                continue
            dong.append({
                'source': 'structure', 'structure_id': s.id,
                'ref_code': (s.code or '') if 'code' in s._fields else '',
                'ref_name': s.name or '', 'amount': s.estimate_value,
            })
        for cl in self.project_cost_line_ids:
            if not cl.amount:
                continue
            cat = cl.category_id
            # Cờ dự phòng gắn ở nhóm CẤP 1 (nhóm 10), mã con không mang
            # cờ — nên phải hỏi cả nhóm gốc.
            du_phong = bool(cat.is_contingency
                            or cat.root_id.is_contingency)
            dong.append({
                'source': 'project_cost',
                'ref_code': cat.code or '',
                'ref_name': cat.display_name or '',
                'amount': cl.amount,
                'is_contingency': du_phong,
            })
        return dong

    @api.depends('structure_ids.estimate_value',
                 'structure_ids.progress_value',
                 'structure_ids.actual_cost',
                 'structure_ids.cost_status',
                 'project_cost_direct_total')
    def _compute_project_evm(self):
        for proj in self:
            structs = proj.structure_ids
            bac = sum(d['amount'] for d in proj._bac_breakdown())
            ev = sum(structs.mapped('progress_value'))
            ac = sum(structs.mapped('actual_cost'))
            cpi = (ev / ac) if ac else 0.0
            eac = (bac / cpi) if cpi else bac
            proj.total_bac = bac
            proj.total_ev = ev
            proj.total_ac = ac
            proj.total_cv = ev - ac
            proj.project_cpi = cpi
            proj.project_eac = eac
            proj.project_vac = bac - eac
            proj.over_budget_count = len(
                structs.filtered(lambda s: s.cost_status == 'over'))
            if not ac or not ev:
                proj.cost_status = 'no_data'
            elif cpi >= 1.0:
                proj.cost_status = 'on_budget'
            elif cpi >= CPI_OVER:
                proj.cost_status = 'watch'
            else:
                proj.cost_status = 'over'
