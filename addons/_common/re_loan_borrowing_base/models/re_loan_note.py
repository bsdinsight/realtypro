# -*- coding: utf-8 -*-
"""KW: cảnh báo (không chặn) khi rút vượt khả dụng thực tế."""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ReLoanNote(models.Model):
    _inherit = 're.loan.note'

    exceeds_available = fields.Boolean(
        string='Vượt khả dụng thực tế',
        compute='_compute_exceeds_available',
        help='Số tiền KW vượt Khả dụng thực tế của facility (theo '
             'borrowing base). CHỈ CẢNH BÁO — NH là bên quyết định '
             'cuối; muốn tăng khả dụng cần nghiệm thu thêm sản lượng '
             'với CĐT hoặc bổ sung TSBĐ.')

    @api.depends('amount', 'facility_id', 'state')
    def _compute_exceeds_available(self):
        for rec in self:
            rec.exceeds_available = bool(
                rec.facility_id
                and rec.state in ('draft', 'sent_to_bank')
                and (rec.facility_id.has_own_pledges
                     or rec.facility_id.credit_contract_id
                     .has_any_pledges)
                and rec.amount
                > rec.facility_id.amount_available_effective + 0.01)


class ReLoanNoteProjectAxis(models.Model):
    """KW gắn DỰ ÁN — nền của 'dư nợ theo dự án'.

    Không có trục này thì khả dụng theo dự án không tính được (không biết
    dự án nào đang chiếm bao nhiêu). Không bắt buộc để tương thích dữ liệu
    cũ; KW không gắn dự án được tính là 'chiếm bể chung'."""
    _inherit = 're.loan.note'

    project_id = fields.Many2one(
        're.project', string='Dự án', index=True, tracking=True,
        help='KW rút vốn cho công trình nào. Nên chọn khi facility có '
             'phân bổ dự án — KW không gắn dự án sẽ ăn vào phần TSBĐ '
             'chung khi tính khả dụng theo dự án.')

    @api.onchange('facility_id')
    def _onchange_facility_project(self):
        # facility chỉ phân bổ đúng 1 dự án -> điền luôn cho khỏi quên
        if self.facility_id and not self.project_id:
            allocs = self.facility_id.project_allocation_ids
            if len(allocs) == 1:
                self.project_id = allocs.project_id


class ReLoanNoteProjectConsistency(models.Model):
    """KW khai dự án → mọi dòng giải ngân phải cùng dự án đó.

    Trước đây KW và dòng giải ngân khai dự án ĐỘC LẬP nhau → có KW dự án
    Vĩnh Bảo mà dòng giải ngân lại ghi Bệnh Viện ABC. Sai kép: hồ sơ tự
    mâu thuẫn, và dư nợ theo dự án (borrowing base) tính sai vì lấy theo
    KW còn chi phí thực lại rơi dự án khác.
    """
    _inherit = 're.loan.note'

    @api.constrains('project_id')
    def _check_disbursement_projects(self):
        for note in self:
            if not note.project_id:
                continue
            bad = note.disbursement_ids.filtered(
                lambda d: d.project_id and d.project_id != note.project_id)
            if bad:
                raise ValidationError(_(
                    'KW %(kw)s khai dự án %(p)s nhưng có %(n)s dòng giải '
                    'ngân đang ghi dự án khác (%(o)s).\nSửa dự án ở các '
                    'dòng giải ngân cho khớp, hoặc bỏ trống dự án trên KW.',
                    kw=note.name, p=note.project_id.display_name,
                    n=len(bad),
                    o=', '.join(bad.mapped('project_id.display_name'))))


class ReLoanNoteOutstandingByProject(models.Model):
    """Dư nợ KW quy về TỪNG DỰ ÁN — nguồn duy nhất cho mọi phép tính
    theo dự án (khả dụng, BB, nhu cầu vốn).

    Hai cách khai dự án đều được ghi nhận (team khách hàng dùng cả hai):
    - KW khai dự án ở ĐẦU PHIẾU → toàn bộ dư nợ gốc thuộc dự án đó.
    - KW KHÔNG khai đầu phiếu, chỉ khai Ở DÒNG GIẢI NGÂN (giải ngân đa
      dự án trên một khế ước) → dư nợ gốc phân bổ theo TỶ TRỌNG số tiền
      giải ngân của từng dự án.

    Vì sao chia theo tỷ trọng: `principal_outstanding` là số CÒN LẠI sau
    khi trả gốc, mà trả gốc không gắn dự án nào — nên phần còn lại được
    quy về các dự án theo đúng tỷ lệ vốn đã rót cho từng dự án.

    Dòng không khai dự án → phần đó vào khoá 0 = "không gắn dự án", tựa
    vào bể TSBĐ chung (thận trọng, không gán bừa cho dự án nào).
    """
    _inherit = 're.loan.note'

    def _outstanding_by_project(self):
        """Trả {project_id: dư nợ gốc}; khoá 0 = không gắn dự án."""
        self.ensure_one()
        out = self.principal_outstanding or 0.0
        if not out:
            return {}
        if self.project_id:
            return {self.project_id.id: out}
        lines = self.disbursement_ids.filtered(
            lambda d: d.state != 'cancelled' and d.amount)
        total = sum(lines.mapped('amount'))
        if not total:
            return {0: out}
        res = {}
        for d in lines:
            key = d.project_id.id or 0
            res[key] = res.get(key, 0.0) + out * (d.amount / total)
        return res

    def _project_share(self, project):
        """Tỷ trọng 0..1 mà KW này thuộc về `project`.

        Dùng cho bảng dòng tiền (§8): một KW có thể rót cho NHIỀU dự án,
        nên nghĩa vụ gốc/lãi từng kỳ phải chia theo đúng tỷ lệ vốn đã rót
        cho dự án — lọc thẳng `note_id.project_id` sẽ bỏ sót KW đa dự án.
        """
        self.ensure_one()
        if not project:
            return 0.0
        if self.project_id:
            return 1.0 if self.project_id == project else 0.0
        lines = self.disbursement_ids.filtered(
            lambda d: d.state != 'cancelled' and d.amount)
        total = sum(lines.mapped('amount'))
        if not total:
            return 0.0
        mine = sum(lines.filtered(
            lambda d: d.project_id == project).mapped('amount'))
        return mine / total
