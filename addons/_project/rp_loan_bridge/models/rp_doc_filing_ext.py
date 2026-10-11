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



class ReLoanNote(models.Model):
    _name = 're.loan.note'
    _inherit = ['re.loan.note', 'rp.doc.filing']

    doc_pending_ids = fields.Many2many(
        'ir.attachment', 're_loan_note_doc_rel',
        'note_id', 'attachment_id', string='Hồ sơ chưa nộp',
        help='Thả tệp vào đây rồi bấm "Nộp vào hồ sơ dự án".')

    def _rp_doc_project(self):
        self.ensure_one()
        return self.facility_id.project_id


class RpLoanDisbursementDossier(models.Model):
    _name = 'rp.loan.disbursement.dossier'
    _inherit = ['rp.loan.disbursement.dossier', 'rp.doc.filing']

    def _rp_doc_nguon_tep(self):
        self.ensure_one()
        return self.attachment_ids

    def _rp_doc_project(self):
        """Dò dự án theo thứ tự ưu tiên, không bám một đường cứng.

        Hồ sơ giải ngân móc vào nhiều chứng từ khác nhau tuỳ loại rút
        vốn, và ``contract_id`` thường TRỐNG — trên SAVA1 cả 5 hồ sơ đều
        trống. Đường thật đi qua khế ước: giải ngân → khế ước → hạn mức
        → dự án.
        """
        self.ensure_one()
        return (self.contract_id.project_id
                or self.acceptance_id.project_id
                or self.disbursement_id.note_id.facility_id.project_id)
