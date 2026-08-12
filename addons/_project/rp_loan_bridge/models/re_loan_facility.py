# -*- coding: utf-8 -*-
"""Hạn mức (facility) gắn THẲNG 1 Dự án + 1 Hợp đồng — mô hình 1-1 của NH.

Anh Đại 2026-08-10: theo ngân hàng, **một facility chỉ tài trợ MỘT hợp
đồng**. Trên form Hạn mức chỉ cần chọn **Dự án**, rồi chọn **hợp đồng
trong danh sách hợp đồng của dự án đó**.

tổng thầu dùng HAI VAI nên "hợp đồng" ở đây là HAI LOẠI chứng từ khác nhau —
xác định theo **NGUỒN TRẢ NỢ** của mục đích vay (anh Đại chốt 2026-08-10,
KHÔNG thêm trường "vai", suy thẳng từ mục đích):

- Nguồn trả nợ = **tiền CĐT thanh toán cho mình** (bảo lãnh thực hiện HĐ,
  vay theo quyền đòi nợ IPC, bao thanh toán bên bán) → gắn **HĐ với CĐT**
  (`rp.owner.contract`). Đây là ca vai TỔNG THẦU.
- Nguồn trả nợ = **tiền mình chi ra cho bên thứ ba** (VLĐ thi công, bao
  thanh toán bên mua, L/C, thiết bị) → gắn **HĐ nhà thầu** (`rp.contract`).
- Mục đích không có hợp đồng đối ứng (đầu tư, VLĐ chung, thấu chi, tái
  cấp vốn…) → **không gắn hợp đồng**, chỉ khai dự án. Cố ép khai sẽ đẻ ra
  hợp đồng ảo.

KHÔNG phải viết lại phần tính toán: hệ thống tự đồng bộ đúng MỘT dòng
trong `re.loan.facility.project.allocation` (cờ `is_auto`) — borrowing
base theo dự án, nhu cầu vốn dự án, checklist giải ngân chạy y nguyên.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Mục đích → loại hợp đồng đối ứng, theo NGUỒN TRẢ NỢ.
PURPOSE_CONTRACT_KIND = {
    # ── CĐT trả tiền cho mình (vai tổng thầu) ──
    'bank_guarantee': 'owner',
    'ar_ipc_loan': 'owner',
    'factoring_seller': 'owner',
    # ── mình chi ra cho bên thứ ba ──
    'wc_construction': 'contractor',
    'wc_material': 'contractor',
    'wc_labor': 'contractor',
    'wc_subcontractor': 'contractor',
    'factoring_buyer': 'contractor',
    'letter_of_credit': 'contractor',
    'lc_import_equipment': 'contractor',
    'trade_finance': 'contractor',
    'equip_purchase': 'contractor',
    'equip_finlease': 'contractor',
    # ── còn lại: không có hợp đồng đối ứng cụ thể ──
    # working_capital, investment_*, dev_*, overdraft, refinance,
    # reimbursement, other → để trống
}


class ReLoanFacility(models.Model):
    _inherit = 're.loan.facility'

    project_id = fields.Many2one(
        're.project', string='Dự án', ondelete='restrict', index=True,
        help='Dự án được tài trợ bởi hạn mức này. Chọn dự án trước để lọc '
             'danh sách hợp đồng.')
    contract_kind = fields.Selection(
        [('owner', 'HĐ với Chủ đầu tư'),
         ('contractor', 'HĐ nhà thầu / nhà cung cấp')],
        string='Loại hợp đồng', compute='_compute_contract_kind',
        store=True, readonly=False,
        help='Tự đặt theo mục đích sử dụng vốn: nguồn trả nợ là tiền CĐT '
             'thanh toán (bảo lãnh, quyền đòi nợ IPC, bao thanh toán bên '
             'bán) → HĐ với CĐT; tiền mình chi ra (VLĐ thi công, L/C, '
             'thiết bị) → HĐ nhà thầu. Sửa được nếu ca đặc thù.')
    owner_contract_id = fields.Many2one(
        'rp.owner.contract', string='HĐ với CĐT', ondelete='restrict',
        index=True, domain="[('project_id', '=', project_id)]",
        help='Hợp đồng ký với chủ đầu tư — chứng từ đối ứng của hạn mức '
             'bảo lãnh thực hiện HĐ và các khoản vay trả bằng tiền CĐT.')
    owner_id = fields.Many2one(
        related='owner_contract_id.owner_id', string='Chủ đầu tư',
        readonly=True)
    owner_contract_value = fields.Monetary(
        related='owner_contract_id.contract_value_total',
        string='Giá trị HĐ CĐT', readonly=True)
    contract_id = fields.Many2one(
        'rp.contract', string='HĐ nhà thầu', ondelete='restrict', index=True,
        domain="[('project_id', '=', project_id)]",
        help='Hợp đồng ký với nhà thầu / nhà cung cấp (xây lắp hoặc mua '
             'hàng hoá) mà hạn mức này tài trợ.')
    contractor_id = fields.Many2one(
        related='contract_id.contractor_id', string='Nhà thầu', readonly=True)
    contract_value_total = fields.Monetary(
        related='contract_id.contract_value_total', string='Giá trị HĐ',
        readonly=True)

    @api.depends('purpose')
    def _compute_contract_kind(self):
        for fac in self:
            fac.contract_kind = PURPOSE_CONTRACT_KIND.get(fac.purpose) or False

    @api.onchange('contract_kind')
    def _onchange_kind_clear_other(self):
        """Đổi loại thì bỏ hợp đồng của loại kia, tránh khai cả hai."""
        if self.contract_kind == 'owner':
            self.contract_id = False
        elif self.contract_kind == 'contractor':
            self.owner_contract_id = False
        else:
            self.contract_id = False
            self.owner_contract_id = False

    @api.onchange('owner_contract_id', 'contract_id')
    def _onchange_contract_fill_project(self):
        ct = self.owner_contract_id or self.contract_id
        if ct:
            self.project_id = ct.project_id

    @api.onchange('project_id')
    def _onchange_project_clear_contract(self):
        if (self.contract_id
                and self.contract_id.project_id != self.project_id):
            self.contract_id = False
        if (self.owner_contract_id
                and self.owner_contract_id.project_id != self.project_id):
            self.owner_contract_id = False

    @api.constrains('owner_contract_id', 'contract_id', 'project_id')
    def _check_contract_project(self):
        for fac in self:
            for ct, label in ((fac.owner_contract_id, _('HĐ với CĐT')),
                              (fac.contract_id, _('HĐ nhà thầu'))):
                if ct and fac.project_id and ct.project_id != fac.project_id:
                    raise ValidationError(_(
                        "%(l)s %(c)s thuộc dự án %(cp)s, không khớp dự án "
                        "%(p)s của hạn mức.",
                        l=label, c=ct.display_name,
                        cp=ct.project_id.display_name,
                        p=fac.project_id.display_name))
            if fac.owner_contract_id and fac.contract_id:
                raise ValidationError(_(
                    "Hạn mức '%s' đang gắn cả HĐ với CĐT lẫn HĐ nhà thầu — "
                    "một hạn mức chỉ ứng với MỘT hợp đồng.", fac.name))

    @api.constrains('owner_contract_id', 'contract_id', 'credit_contract_id')
    def _check_contract_unique_in_credit_contract(self):
        """Vế còn lại của quan hệ 1-1: trong CÙNG một HĐTD, mỗi hợp đồng
        chỉ được MỘT hạn mức nhận (anh Đại chốt 2026-08-10).

        Không chặn giữa các HĐTD khác nhau — cùng một hợp đồng vẫn có thể
        được tài trợ bởi hạn mức ở HĐTD của ngân hàng khác.
        """
        for fac in self:
            cc = fac.credit_contract_id
            if not cc:
                continue
            for fname, label in (('contract_id', _('HĐ nhà thầu')),
                                 ('owner_contract_id', _('HĐ với CĐT'))):
                ct = fac[fname]
                if not ct:
                    continue
                dup = self.search([
                    ('id', '!=', fac.id),
                    ('credit_contract_id', '=', cc.id),
                    (fname, '=', ct.id)], limit=1)
                if dup:
                    raise ValidationError(_(
                        "%(l)s '%(c)s' đã được gắn cho hạn mức '%(d)s' "
                        "trong HĐTD %(cc)s — mỗi hợp đồng chỉ ứng với MỘT "
                        "hạn mức. Sửa hạn mức '%(d)s' hoặc chọn hợp đồng "
                        "khác cho '%(f)s'.",
                        l=label, c=ct.display_name, d=dup.name,
                        cc=cc.display_name, f=fac.name or _('hạn mức này')))

    # ------------------------------------------------------------------
    def _sync_auto_allocation(self):
        """Giữ đúng MỘT dòng phân bổ tự sinh khớp dự án/HĐ của facility.

        Dòng người dùng tự nhập (is_auto = False) không bị đụng tới.
        """
        Alloc = self.env['re.loan.facility.project.allocation'].sudo()
        for fac in self:
            auto = Alloc.search(
                [('facility_id', '=', fac.id), ('is_auto', '=', True)],
                limit=1)
            proj = fac.project_id or fac.owner_contract_id.project_id \
                or fac.contract_id.project_id
            if not proj:
                if auto:
                    auto.unlink()
                continue
            vals = {
                'facility_id': fac.id,
                'project_id': proj.id,
                # dòng phân bổ chỉ mang HĐ nhà thầu (nền quy dư nợ theo HĐ);
                # hạn mức gắn HĐ với CĐT thì để trống, tính ở cấp dự án.
                'contract_id': fac.contract_id.id or False,
                'amount': fac.amount_limit or 0.0,
                'is_auto': True,
                'description': _('Tự đồng bộ từ hạn mức (1 hạn mức = 1 HĐ)'),
            }
            if auto:
                auto.write(vals)
            else:
                Alloc.create(vals)

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._sync_auto_allocation()
        return recs

    def write(self, vals):
        res = super().write(vals)
        if {'project_id', 'contract_id', 'owner_contract_id',
                'amount_limit'} & set(vals):
            self._sync_auto_allocation()
        return res
