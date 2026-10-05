# -*- coding: utf-8 -*-
"""Hồ sơ nhìn từ hợp đồng: hạn xem xét, việc đang chờ, và cổng bàn giao.

Hai câu hỏi hợp đồng nào cũng phải trả lời được:

* "Bên mình có đang giữ hồ sơ của nhà thầu quá hạn không" — vì quá hạn
  xem xét là lỗi của chủ đầu tư, và nhà thầu sẽ dùng đúng số ngày đó để
  đòi gia hạn.
* "Đã đủ hồ sơ để cấp chứng chỉ bàn giao chưa" — điều 5.6 và 5.7 nói
  công trình CHƯA được coi là hoàn thành cho mục đích bàn giao khi chưa
  nhận đủ hồ sơ hoàn công và tài liệu vận hành. Hiện trường xong mà hồ sơ
  thiếu thì ngày bàn giao vẫn chưa chạy, và phạt chậm vẫn đếm.
"""
from odoo import _, api, fields, models

CLEARED_STATES = ('approved', 'approved_comment')

# Bộ hồ sơ khởi tạo theo điều 5.2 / 5.6 / 5.7 — dùng khi chưa có ma trận
# hồ sơ của hợp đồng (Annex 16). Mỗi dòng: tên, loại, luồng trình, bộ môn.
STARTER_REGISTER = [
    ('Kế hoạch quản lý chất lượng dự án', 'qa_qc', 'approval', 'other'),
    ('Kế hoạch an toàn — sức khoẻ — môi trường', 'hse', 'approval', 'hse'),
    ('Tiến độ thi công chi tiết', 'other', 'approval', 'other'),
    ('Báo cáo khảo sát địa chất, địa hình', 'calculation', 'review',
     'civil'),
    ('Thiết kế kỹ thuật — nền móng', 'design', 'approval', 'civil'),
    ('Tính toán kết cấu móng', 'calculation', 'approval', 'civil'),
    ('Thiết kế kỹ thuật — kết cấu, lắp dựng', 'design', 'approval',
     'structural'),
    ('Thiết kế kỹ thuật — điện, trạm biến áp', 'design', 'approval',
     'electrical'),
    ('Sơ đồ một sợi, bảo vệ, đấu nối', 'design', 'approval', 'electrical'),
    ('Thiết kế SCADA, điều khiển, thông tin', 'design', 'approval', 'scada'),
    ('Đặc tính kỹ thuật vật tư, thiết bị chính', 'spec', 'approval',
     'other'),
    ('Biện pháp thi công các công tác chính', 'method', 'approval', 'other'),
    ('Kế hoạch vận chuyển, cẩu lắp thiết bị siêu trường', 'method',
     'approval', 'structural'),
    ('Quy trình thí nghiệm, chạy thử, nghiệm thu', 'test', 'approval',
     'other'),
    ('Hồ sơ xin phép, thủ tục pháp lý', 'permit', 'review', 'other'),
    ('Hồ sơ hoàn công', 'as_built', 'review', 'other'),
    ('Tài liệu vận hành & bảo trì', 'om_manual', 'review', 'other'),
]


class RpContract(models.Model):
    _inherit = 'rp.contract'

    doc_review_days = fields.Integer(
        string='Hạn xem xét hồ sơ (ngày)', default=21,
        help='Điều 5.2: thời hạn xem xét không quá 21 ngày, trừ khi Yêu '
             'cầu của chủ đầu tư quy định khác. Hồ sơ mới lấy mặc định '
             'theo con số này.')
    document_ids = fields.One2many(
        'rp.document', 'contract_id', string='Hồ sơ kỹ thuật')
    document_count = fields.Integer(string='Số hồ sơ',
                                    compute='_compute_document_rollup')
    doc_pending_count = fields.Integer(
        string='Hồ sơ đang xem xét', compute='_compute_document_rollup')
    doc_not_submitted_count = fields.Integer(
        string='Hồ sơ chưa trình', compute='_compute_document_rollup')
    doc_rejected_count = fields.Integer(
        string='Hồ sơ bị trả lại', compute='_compute_document_rollup')
    # Cổng bàn giao thì LƯU, vì nó phải lọc được trên danh sách hợp đồng
    # và không phụ thuộc ngày hôm nay. Để riêng một hàm tính: trộn trường
    # lưu và không lưu trong cùng một compute là tự tạo ghi ngoài ý muốn.
    doc_toc_outstanding_count = fields.Integer(
        string='Hồ sơ còn thiếu để bàn giao', compute='_compute_toc_gate',
        store=True)
    toc_doc_ready = fields.Boolean(
        string='Đủ hồ sơ để bàn giao', compute='_compute_toc_gate',
        store=True,
        help='Chỉ đúng khi mọi hồ sơ được đánh dấu "phải có trước khi bàn '
             'giao" đều đã được duyệt — điều kiện của điều 5.6 và 5.7.')

    @api.depends('document_ids.state')
    def _compute_document_rollup(self):
        for rec in self:
            docs = rec.document_ids.filtered(
                lambda d: d.state != 'cancelled')
            rec.document_count = len(docs)
            rec.doc_pending_count = len(
                docs.filtered(lambda d: d.state == 'submitted'))
            rec.doc_not_submitted_count = len(
                docs.filtered(lambda d: d.state == 'planned'))
            rec.doc_rejected_count = len(
                docs.filtered(lambda d: d.state == 'rejected'))

    @api.depends('document_ids.state', 'document_ids.is_toc_required')
    def _compute_toc_gate(self):
        for rec in self:
            toc = rec.document_ids.filtered(
                lambda d: d.is_toc_required and d.state != 'cancelled')
            outstanding = toc.filtered(
                lambda d: d.state not in CLEARED_STATES)
            rec.doc_toc_outstanding_count = len(outstanding)
            rec.toc_doc_ready = bool(toc) and not outstanding

    def action_open_documents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Hồ sơ kỹ thuật — %s', self.name),
            'res_model': 'rp.document',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id,
                        'default_project_id': self.project_id.id,
                        'default_review_days': self.doc_review_days or 21},
        }

    def action_seed_document_register(self):
        """Tạo bộ hồ sơ khởi tạo theo điều 5.2 / 5.6 / 5.7.

        Chưa có ma trận hồ sơ của hợp đồng thì bắt đầu từ bộ này rồi sửa,
        nhanh hơn là gõ từ đầu. Bộ khởi tạo cố ý chỉ gồm những hồ sơ mà
        hợp đồng dạng thiết kế–thi công nào cũng đòi; phần riêng của từng
        hợp đồng phải lấy từ Annex 16.
        """
        Document = self.env['rp.document']
        created = Document
        for rec in self:
            have = set(rec.document_ids.mapped('name'))
            for name, doc_type, track, discipline in STARTER_REGISTER:
                if name in have:
                    continue
                created |= Document.create({
                    'name': name,
                    'doc_type': doc_type,
                    'review_track': track,
                    'discipline': discipline,
                    'project_id': rec.project_id.id,
                    'contract_id': rec.id,
                    'review_days': rec.doc_review_days or 21,
                    'is_toc_required': doc_type in ('as_built', 'om_manual'),
                })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Hồ sơ kỹ thuật'),
            'res_model': 'rp.document',
            'view_mode': 'list,form',
            'domain': [('id', 'in', created.ids)],
        }
