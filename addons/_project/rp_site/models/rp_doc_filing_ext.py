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



class RpSiteDiary(models.Model):
    _name = 'rp.site.diary'
    _inherit = ['rp.site.diary', 'rp.doc.filing']

    def _rp_doc_nguon_tep(self):
        self.ensure_one()
        return self.attachment_ids


class RpSitePunch(models.Model):
    _name = 'rp.site.punch'
    _inherit = ['rp.site.punch', 'rp.doc.filing']

    def _rp_doc_nguon_tep(self):
        self.ensure_one()
        return self.attachment_ids


class RpSiteToolbox(models.Model):
    _name = 'rp.site.toolbox'
    _inherit = ['rp.site.toolbox', 'rp.doc.filing']

    def _rp_doc_nguon_tep(self):
        self.ensure_one()
        return self.attachment_ids


class RpSiteIncident(models.Model):
    _name = 'rp.site.incident'
    _inherit = ['rp.site.incident', 'rp.doc.filing']

    def _rp_doc_nguon_tep(self):
        self.ensure_one()
        return self.attachment_ids


class RpSiteSafetyInspection(models.Model):
    _name = 'rp.site.safety.inspection'
    _inherit = ['rp.site.safety.inspection', 'rp.doc.filing']

    def _rp_doc_nguon_tep(self):
        self.ensure_one()
        return self.attachment_ids
