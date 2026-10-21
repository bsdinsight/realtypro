# -*- coding: utf-8 -*-
"""Dựng sổ cái nghĩa vụ từ các sổ chuyên đã có.

Đồng bộ chứ không chép
----------------------
Việc ở đây chỉ là **tạo đúng một dòng chỉ mục** cho mỗi (bản ghi, vai).
Hạn và trạng thái thì ``rp.obligation`` tự đọc từ bản ghi gốc mỗi lần
tính — nên dòng chỉ mục có cũ mấy cũng không bao giờ sai hạn. Thứ duy
nhất cũ đi được là *thiếu dòng* cho bản ghi vừa tạo, và đó là việc của
nút đồng bộ cộng một lịch chạy đêm.

Vì sao không móc vào ``create`` của năm model
----------------------------------------------
Móc vào thì mỗi lần tạo hồ sơ/phát sinh/khiếu nại đều kéo theo một lần
ghi sang model khác — năm điểm chèn, năm đường vỡ, và lỗi ở sổ cái sẽ
chặn luôn nghiệp vụ gốc. Sổ cái là thứ *đọc*, không đáng để chặn người
đang nhập liệu. Lịch đêm cộng nút bấm tay là đủ, và hỏng thì không ai
mất việc đang làm.
"""
from odoo import _, api, fields, models

#: Điều khoản FIDIC hay gặp cho từng loại nghĩa vụ. CHỈ dùng để nối khi
#: hợp đồng đã khai đúng số điều đó — không tự tạo điều khoản, không
#: đoán. Hợp đồng đánh số khác thì đơn giản là không nối, và màn hình
#: hiện ra là "chưa neo điều khoản" chứ không neo bừa vào điều sai.
DIEU_THEO_VAI = {
    'trinh': '5.2',
    'xem_xet': '5.2',
    'bao_gia': '13.3',
}

#: Model gốc → tên trường trỏ tới nó trên ``rp.obligation``.
TRUONG_THEO_MODEL = {
    'rp.document': 'document_id',
    'rp.variation': 'variation_id',
    'rp.claim': 'claim_id',
    'rp.contract.guarantee': 'guarantee_id',
    'rp.contract.payment.milestone': 'milestone_id',
}


class RpContract(models.Model):
    _inherit = 'rp.contract'

    clause_ids = fields.One2many(
        'rp.contract.clause', 'contract_id', string='Điều khoản')
    clause_count = fields.Integer(
        string='Số điều khoản', compute='_compute_nghia_vu_count')

    obligation_ids = fields.One2many(
        'rp.obligation', 'contract_id', string='Nghĩa vụ')
    obligation_count = fields.Integer(
        string='Số nghĩa vụ', compute='_compute_nghia_vu_count')
    obligation_qua_han = fields.Integer(
        string='Nghĩa vụ quá hạn', compute='_compute_nghia_vu_count')
    obligation_sap_den = fields.Integer(
        string='Nghĩa vụ sắp đến hạn', compute='_compute_nghia_vu_count')
    obligation_chua_neo = fields.Integer(
        string='Chưa neo điều khoản', compute='_compute_nghia_vu_count',
        help='Nghĩa vụ chưa trỏ được vào điều khoản nào. Con số này nói '
             'thẳng là sổ điều khoản còn trống tới đâu, thay vì để màn '
             'hình trông như đã đủ.')

    def _compute_nghia_vu_count(self):
        Ob = self.env['rp.obligation']
        gom = Ob._read_group(
            [('contract_id', 'in', self.ids)],
            ['contract_id', 'trang_thai'], ['__count'])
        theo_hd = {}
        for hd, tt, n in gom:
            theo_hd.setdefault(hd.id, {})[tt] = n
        chua_neo = {hd.id: n for hd, n in Ob._read_group(
            [('contract_id', 'in', self.ids), ('clause_id', '=', False)],
            ['contract_id'], ['__count'])}
        dieu = {hd.id: n for hd, n in self.env['rp.contract.clause']._read_group(
            [('contract_id', 'in', self.ids)], ['contract_id'], ['__count'])}
        for rec in self:
            d = theo_hd.get(rec.id, {})
            rec.obligation_count = sum(d.values())
            rec.obligation_qua_han = d.get('qua_han', 0)
            rec.obligation_sap_den = d.get('sap_den', 0)
            rec.obligation_chua_neo = chua_neo.get(rec.id, 0)
            rec.clause_count = dieu.get(rec.id, 0)

    # ======================================================================
    # Đồng bộ
    # ======================================================================
    def _thu_thap_nghia_vu(self):
        """[(khoa, vals)] cho mọi nghĩa vụ suy ra được từ các sổ chuyên."""
        self.ensure_one()
        ra = []

        def them(goc, vai, ben, loai, ten):
            ra.append(('%s-%s-%s' % (goc._name, goc.id, vai), {
                'name': ten,
                'contract_id': self.id,
                'vai': vai,
                'ben': ben,
                'loai': loai,
                TRUONG_THEO_MODEL[goc._name]: goc.id,
            }))

        for d in self.env['rp.document'].search(
                [('contract_id', '=', self.id)]):
            nhan = d.name or d.code or _('Hồ sơ #%s', d.id)
            them(d, 'trinh', 'nha_thau', 'ho_so',
                 _('Nộp hồ sơ: %s', nhan))
            them(d, 'xem_xet', 'chu_dau_tu', 'xem_xet',
                 _('Trả lời hồ sơ: %s', nhan))

        for v in self.env['rp.variation'].search(
                [('contract_id', '=', self.id)]):
            them(v, 'bao_gia', 'nha_thau', 'phat_sinh',
                 _('Nộp báo giá phát sinh: %s', v.name or v.code or v.id))

        for c in self.env['rp.claim'].search(
                [('contract_id', '=', self.id)]):
            ben = ('nha_thau' if c.direction == 'from_contractor'
                   else 'chu_dau_tu')
            them(c, 'thong_bao', ben, 'khieu_nai',
                 _('Gửi thông báo khiếu nại: %s', c.name or c.code or c.id))

        for g in self.env['rp.contract.guarantee'].search(
                [('contract_id', '=', self.id)]):
            them(g, 'duy_tri', 'nha_thau', 'bao_lanh',
                 _('Duy trì hiệu lực bảo lãnh: %s', g.name or g.id))

        for m in self.env['rp.contract.payment.milestone'].search(
                [('contract_id', '=', self.id)]):
            them(m, 'thanh_toan', 'chu_dau_tu', 'thanh_toan',
                 _('Thanh toán mốc: %s', m.name or m.id))

        return ra

    def _neo_dieu_khoan(self, vals):
        """Nối vào điều khoản CHỈ KHI hợp đồng đã khai đúng số điều đó."""
        so = DIEU_THEO_VAI.get(vals.get('vai'))
        if not so:
            return
        dieu = self.env['rp.contract.clause'].search([
            ('contract_id', '=', self.id),
            ('number', '=', so),
            ('is_current', '=', True)], limit=1)
        if dieu:
            vals['clause_id'] = dieu.id

    def action_dong_bo_nghia_vu(self):
        """Dựng lại sổ cái nghĩa vụ — chạy bao nhiêu lần cũng ra một kết quả."""
        Ob = self.env['rp.obligation']
        them = sua = 0
        for hd in self:
            muon = dict(hd._thu_thap_nghia_vu())
            dang_co = {o.khoa: o for o in Ob.search([
                ('contract_id', '=', hd.id), ('khoa', '!=', False)])}
            moi = []
            for khoa, vals in muon.items():
                hd._neo_dieu_khoan(vals)
                cu = dang_co.get(khoa)
                if not cu:
                    moi.append(vals)
                    continue
                # Chỉ ghi khi thực sự khác — tránh đẻ ra một dòng chatter
                # mỗi đêm cho mọi nghĩa vụ trong hệ thống.
                doi = {k: v for k, v in vals.items()
                       if k in ('name', 'ben', 'loai')
                       and cu[k] != v}
                if not cu.clause_id and vals.get('clause_id'):
                    doi['clause_id'] = vals['clause_id']
                if doi:
                    cu.write(doi)
                    sua += 1
            if moi:
                Ob.create(moi)
                them += len(moi)
        return {'them': them, 'sua': sua}

    def action_dong_bo_nghia_vu_ui(self):
        kq = self.action_dong_bo_nghia_vu()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'title': _('Đã đồng bộ sổ nghĩa vụ'),
                'message': _('Thêm %(t)s, cập nhật %(s)s. Hạn và tình trạng '
                             'luôn đọc thẳng từ sổ gốc nên không cần đồng '
                             'bộ lại khi sửa hạn.',
                             t=kq['them'], s=kq['sua']),
                'sticky': False,
            },
        }

    def action_xem_nghia_vu(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Nghĩa vụ — %s', self.name),
            'res_model': 'rp.obligation',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id,
                        'search_default_group_loai': 1},
        }

    def action_xem_dieu_khoan(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Điều khoản — %s', self.name),
            'res_model': 'rp.contract.clause',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id},
        }

    @api.model
    def cron_dong_bo_nghia_vu(self):
        """Lịch đêm: bắt những bản ghi mới tạo trong ngày."""
        hd = self.search([('state', 'in',
                           ('signed', 'executing', 'completed'))])
        kq = hd.action_dong_bo_nghia_vu()
        if kq['them'] or kq['sua']:
            self.env['ir.logging'].sudo().create({
                'name': 'rp_obligation',
                'type': 'server',
                'level': 'INFO',
                'dbname': self.env.cr.dbname,
                'message': 'Đồng bộ sổ nghĩa vụ: thêm %s, sửa %s trên %s '
                           'hợp đồng.' % (kq['them'], kq['sua'], len(hd)),
                'path': 'rp_obligation',
                'func': 'cron_dong_bo_nghia_vu',
                'line': '0',
            })
        return True
