# -*- coding: utf-8 -*-
"""Nối các sổ của module này vào thư mục hồ sơ dự án (mixin rp.doc.filing).

Để riêng một tệp thay vì sửa thẳng model gốc: phần nối này là chuyện của
cây thư mục, không phải chuyện của nghiệp vụ sổ. Tách ra thì đọc model
gốc không bị lẫn, và gỡ ra cũng chỉ một tệp.

Sổ nào đã có sẵn ô đính kèm thì DÙNG LẠI ô đó (``_rp_doc_nguon_tep``) —
hai hộp thả tệp cạnh nhau thì không ai đoán được hộp nào đi lên
SharePoint. Sổ nào chưa có thì khai ô mới, kèm ``relation=`` TƯỜNG MINH:
mixin không khai Many2many ir.attachment hộ được, vì model nào đã sẵn có
một m2m ir.attachment khác sẽ trùng tên bảng và sập cả registry.
"""
from odoo import fields, models



class RpConceptEstimate(models.Model):
    _name = 'rp.concept.estimate'
    _inherit = ['rp.concept.estimate', 'rp.doc.filing']

    doc_pending_ids = fields.Many2many(
        'ir.attachment', 'rp_concept_estimate_doc_rel',
        'estimate_id', 'attachment_id', string='Hồ sơ chưa nộp',
        help='Thả tệp vào đây rồi bấm "Nộp vào hồ sơ dự án".')


class RpTenderPackage(models.Model):
    _name = 'rp.tender.package'
    _inherit = ['rp.tender.package', 'rp.doc.filing']

    def _rp_doc_nguon_tep(self):
        self.ensure_one()
        return self.hsmt_attachment_ids


class RpTenderBidder(models.Model):
    _name = 'rp.tender.bidder'
    _inherit = ['rp.tender.bidder', 'rp.doc.filing']

    doc_pending_ids = fields.Many2many(
        'ir.attachment', 'rp_tender_bidder_doc_rel',
        'bidder_id', 'attachment_id', string='Hồ sơ chưa nộp',
        help='Thả tệp vào đây rồi bấm "Nộp vào hồ sơ dự án".')
