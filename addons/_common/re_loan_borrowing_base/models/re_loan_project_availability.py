# -*- coding: utf-8 -*-
"""Khả dụng theo DỰ ÁN trên từng dòng phân bổ facility — spec nghiệp vụ khối 2.

Hai chiều cắt nhau — DỰ ÁN (TSBĐ của dự án nào gánh dự án đó) và CẤP CẦM CỐ
(cầm cố riêng facility thì chỉ facility đó dùng). Đã chốt với anh Đại:
- TSBĐ dự án cầm cố CẤP FACILITY → ring-fence cho đúng facility đó. Đây là
  cách "phân bổ base vào facility" siết được khả dụng của từng facility.
- TSBĐ dự án cầm cố CẤP HĐTD → bể riêng của dự án, mọi facility của HĐTD
  dùng chung; facility nào có dư nợ vượt phần ring-fence của mình thì tựa
  vào bể này trước (giữ nguyên fix: IPC cầm cố "toàn hợp đồng" vẫn đếm).
- TSBĐ CHUNG (không gắn dự án) = bể ngoài cùng; dự án nào có dư nợ VƯỢT BB
  riêng thì phần vượt tựa vào đây. Phần còn trống mới chia cho dự án đang
  hỏi. KW không gắn dự án → toàn bộ dư nợ tựa vào bể chung (thận trọng).

Khả dụng(dự án P tại facility F)
    = max(0, phân bổ(F,P) + BB riêng dự án(F,P) − dư nợ(F,P))

trong đó **BB riêng dự án(F,P) = ring-fence(F,P) + bể cấp HĐTD của P còn
trống**. Anh Đại chốt (nêu 3 lần): TSBĐ của dự án là NGUỒN CỘNG THÊM,
KHÔNG phải trần — **không cap** bằng hạn mức còn của facility, cũng không
cap bằng umbrella HĐTD. Hệ quả có chủ đích: cột này có thể lớn hơn cả số
phân bổ lẫn hạn mức facility; nó là số QUẢN TRỊ.
Chốt chặn thật không nằm ở đây mà ở `re_loan`: constraint trên khế ước
chặn KW vượt hạn mức còn lại của facility; thêm cờ `project_margin_call`
cảnh báo khi dư nợ dự án vượt TSBĐ của nó.

Các dòng dự án KHÔNG cộng được với nhau — bể chung là dùng chung, mỗi dòng
trả lời "dự án này rút TỐI ĐA được bao nhiêu ngay bây giờ".
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ReLoanFacilityProjectAllocation(models.Model):
    _inherit = 're.loan.facility.project.allocation'

    amount_used_project = fields.Monetary(
        string='Dư nợ dự án', compute='_compute_project_numbers',
        help='Σ dư nợ gốc các KW của dự án này trên facility '
             '(KW nháp/huỷ/tất toán không tính).')
    borrowing_base_project = fields.Monetary(
        string='BB riêng dự án', compute='_compute_project_numbers',
        help='Borrowing base của dự án này DÙNG ĐƯỢC TẠI facility này = '
             'phần TSBĐ cầm cố riêng cho facility (ring-fence, ví dụ IPC '
             'phân bổ vào facility) + phần bể cấp HĐTD của dự án còn '
             'trống sau khi các facility khác đã tựa vào.')
    shared_headroom = fields.Monetary(
        string='Bể chung còn trống', compute='_compute_project_numbers',
        help='TSBĐ KHÔNG gắn dự án mà facility này với tới được, trừ phần '
             'các dự án khác (và KW không gắn dự án) đang tựa vào.')
    amount_available_project = fields.Monetary(
        string='Khả dụng dự án', compute='_compute_project_numbers',
        help='Số dự án này rút được NGAY = số NHỎ NHẤT của: ① phân bổ − '
             'dư nợ dự án · ② TSBĐ riêng dự án (+ bể chung với tới được) '
             '− dư nợ dự án · ③ hạn mức còn của facility và TSBĐ chung '
             'toàn HĐTD.\nBằng 0 dù hạn mức còn là ĐÚNG nghiệp vụ (tài '
             'liệu tài liệu nghiệp vụ §9.8): dư nợ đã dùng hết TSBĐ. Xem cột "Đang bị '
             'chặn bởi" để biết phải xử lý gì.')
    blocked_by = fields.Selection(
        [('none', 'Không bị chặn'),
         ('limit', 'Hạn mức phân bổ cho dự án'),
         ('collateral', 'TSBĐ riêng dự án'),
         ('facility', 'Hạn mức còn của facility'),
         ('umbrella', 'TSBĐ chung toàn HĐTD')],
        string='Đang bị chặn bởi', compute='_compute_project_numbers',
        help='Nhánh nào đang quyết định con số khả dụng — biết chỗ nghẽn '
             'thì mới biết xử lý: thiếu TSBĐ thì bổ sung IPC được CĐT ký '
             '/ thu hồi công nợ; thiếu hạn mức thì đàm phán với NH.')
    unlock_gap = fields.Monetary(
        string='Cần thêm để mở khoá', compute='_compute_project_numbers',
        help='Bù thêm chừng này vào đúng nhánh đang chặn thì khả dụng mới '
             'nhích lên (đến khi chạm nhánh kế tiếp). Ví dụ tài liệu nghiệp vụ '
             '§9.9: thiếu 48 tỷ TSBĐ → thêm IPC 80 tỷ được CĐT ký (tỷ lệ '
             'cho vay 60%) là mở khoá đúng 48 tỷ.')

    # ── tổng theo DỰ ÁN trên toàn HĐTD (lặp giá trị ở mọi dòng cùng
    #    dự án — để đọc ngay trên bảng, không phải tự cộng) ──
    project_limit_total = fields.Monetary(
        string='Tổng hạn mức dự án', compute='_compute_project_totals',
        help='Σ số tiền phân bổ cho dự án này trên MỌI facility của cùng '
             'HĐTD.')
    project_used_total = fields.Monetary(
        string='Tổng dư nợ dự án', compute='_compute_project_totals',
        help='Σ dư nợ gốc các KW của dự án này trên toàn HĐTD.')
    project_available_total = fields.Monetary(
        string='Tổng khả dụng dự án', compute='_compute_project_totals',
        help='Σ khả dụng của dự án qua các facility, NHƯNG bị CAP bởi '
             'phần umbrella còn lại của HĐTD (borrowing base tổng − dư '
             'nợ tổng). Không phải phép cộng đơn thuần: các facility '
             'dùng chung bể TSBĐ nên cộng thẳng sẽ thổi phồng.')

    @api.depends('facility_id', 'project_id', 'amount',
                 'amount_available_project')
    def _compute_project_totals(self):
        Alloc = self.env['re.loan.facility.project.allocation']
        for rec in self:
            contract = rec.facility_id.credit_contract_id
            if not contract or not rec.project_id:
                rec.project_limit_total = 0.0
                rec.project_used_total = 0.0
                rec.project_available_total = 0.0
                continue
            siblings = Alloc.search([
                ('project_id', '=', rec.project_id.id),
                ('facility_id.credit_contract_id', '=', contract.id)])
            rec.project_limit_total = sum(siblings.mapped('amount'))
            bb_fac, bb_con, used_fac = self._contract_pledge_split(contract)
            pid = rec.project_id.id
            bb_total_by, used_total_by = {}, {}
            for (_f, p), v in bb_fac.items():
                bb_total_by[p] = bb_total_by.get(p, 0.0) + v
            for p, v in bb_con.items():
                bb_total_by[p] = bb_total_by.get(p, 0.0) + v
            for (_f, p), v in used_fac.items():
                used_total_by[p] = used_total_by.get(p, 0.0) + v
            rec.project_used_total = used_total_by.get(pid, 0.0)
            # Cộng thẳng các dòng, KHÔNG cap — để tổng luôn khớp với những
            # gì user cộng tay từ cột "Khả dụng dự án" (đã bỏ mọi trần theo
            # quyết định của anh Đại). Trần thật vẫn nằm ở constraint KW.
            rec.project_available_total = max(
                0.0, sum(siblings.mapped('amount_available_project')))
    project_margin_call = fields.Boolean(
        string='Thiếu bảo đảm', compute='_compute_project_numbers',
        help='Dư nợ dự án đã vượt (BB riêng + phần bể chung) — cần thêm '
             'IPC được CĐT ký hoặc trả bớt nợ.')

    def _used_by_contract(self, fac, contract_ids):
        """{contract_id: dư nợ gốc} của các HĐ nhà thầu tại facility `fac`.

        Nền của "phân bổ tới hợp đồng, dự án tự suy ra" (anh Đại chốt
        2026-08-04): dòng phân bổ gắn hợp đồng thì chỉ gánh dư nợ của đúng
        hợp đồng đó, không gánh cả dự án.
        """
        if not contract_ids:
            return {}
        live = fac.note_ids.filtered(
            lambda n: n.state not in ('draft', 'cancelled', 'fully_paid'))
        res = {}
        for n in live:
            for cid, amt in n._outstanding_by_contract().items():
                if cid in contract_ids:
                    res[cid] = res.get(cid, 0.0) + amt
        return res

    def _contract_pledge_split(self, contract):
        """Tách TSBĐ theo CẤP cầm cố — nền của quy tắc "phân bổ theo facility".

        Anh Đại chốt 2026-07-30: phân bổ base vào facility phải siết luôn
        "Khả dụng dự án" của chính facility đó. Muốn vậy phải phân biệt:
        - pledge cấp FACILITY  → chỉ facility ĐÓ được dùng (ring-fence);
        - pledge cấp HĐTD      → bể của cả HĐTD, mọi facility dùng chung
          (giữ nguyên fix bug #7: IPC cầm cố "toàn hợp đồng" vẫn đếm).
        Cắt chéo thêm chiều DỰ ÁN: TSBĐ của dự án X chỉ gánh dự án X, TSBĐ
        không gắn dự án là "bể chung" mọi dự án tựa vào.

        Trả dict:
          bb_fac  {(facility_id, project_id): base}   project_id 0 = TSBĐ chung
          bb_con  {project_id: base}                  cầm cố cấp HĐTD
          used    {(facility_id, project_id): dư nợ gốc}
        """
        Pledge = self.env['re.loan.collateral.pledge']
        pledges = Pledge.search([
            ('state', '=', 'active'), ('advance_rate', '>', 0),
            '|',
            '&', ('pledge_target', '=', 'contract'),
                 ('credit_contract_id', '=', contract.id),
            '&', ('pledge_target', '=', 'facility'),
                 ('facility_id.credit_contract_id', '=', contract.id),
        ])
        bb_fac, bb_con = {}, {}
        for p in pledges:
            pid = p.collateral_id.project_id.id or 0
            val = p.base_contribution or 0.0
            if p.pledge_target == 'facility':
                key = (p.facility_id.id, pid)
                bb_fac[key] = bb_fac.get(key, 0.0) + val
            else:
                bb_con[pid] = bb_con.get(pid, 0.0) + val
        used = {}
        notes = self.env['re.loan.note'].search([
            ('facility_id.credit_contract_id', '=', contract.id),
            ('state', 'not in', ('draft', 'cancelled', 'fully_paid'))])
        for n in notes:
            for pid, amt in n._outstanding_by_project().items():
                key = (n.facility_id.id, pid)
                used[key] = used.get(key, 0.0) + amt
        return bb_fac, bb_con, used

    def _contract_pledge_data(self, contract):
        """Pledge active có tỷ lệ trên TOÀN HĐTD, gom theo dự án.

        Trả (bb_by_project: {project_id: Σ contribution, 0 = TSBĐ CHUNG},
             used_by_project: {project_id: Σ dư nợ gốc KW sống, 0 = không
             gắn dự án}).
        TSBĐ cầm cố Ở CẤP HĐTD của dự án nào vẫn RING-FENCE cho dự án đó
        (quyền đòi nợ dự án X chỉ gánh dự án X) — chỉ khác là dùng được ở
        mọi facility của HĐTD. Đây là chỗ bug cũ: chỉ đọc pledge cấp
        facility nên bỏ sót toàn bộ TSBĐ cầm cố "toàn HĐTD".
        """
        Pledge = self.env['re.loan.collateral.pledge']
        pledges = Pledge.search([
            ('state', '=', 'active'), ('advance_rate', '>', 0),
            '|',
            '&', ('pledge_target', '=', 'contract'),
                 ('credit_contract_id', '=', contract.id),
            '&', ('pledge_target', '=', 'facility'),
                 ('facility_id.credit_contract_id', '=', contract.id),
        ])
        bb_by = {}
        for p in pledges:
            key = p.collateral_id.project_id.id or 0
            bb_by[key] = bb_by.get(key, 0.0) + (p.base_contribution or 0.0)
        used_by = {}
        notes = self.env['re.loan.note'].search([
            ('facility_id.credit_contract_id', '=', contract.id),
            ('state', 'not in', ('draft', 'cancelled', 'fully_paid'))])
        for n in notes:
            # KW khai dự án đầu phiếu HOẶC chỉ khai ở dòng giải ngân —
            # cả hai đều được quy về dự án qua helper.
            for pid, amt in n._outstanding_by_project().items():
                used_by[pid] = used_by.get(pid, 0.0) + amt
        return bb_by, used_by

    @api.depends('facility_id', 'project_id', 'amount', 'contract_id',
                 'facility_id.note_ids.disbursement_ids.contract_id',
                 'facility_id.note_ids.principal_outstanding',
                 'facility_id.note_ids.state',
                 'facility_id.note_ids.project_id',
                 'facility_id.note_ids.disbursement_ids.project_id',
                 'facility_id.note_ids.disbursement_ids.amount',
                 'facility_id.note_ids.disbursement_ids.state',
                 'facility_id.facility_pledge_ids.base_contribution',
                 'facility_id.facility_pledge_ids.state')
    def _compute_project_numbers(self):
        for rec in self:
            fac = rec.facility_id
            proj = rec.project_id
            contract = fac.credit_contract_id if fac else False
            if not fac or not proj or not contract:
                rec.update({'amount_used_project': 0.0,
                            'borrowing_base_project': 0.0,
                            'shared_headroom': 0.0,
                            'amount_available_project': 0.0,
                            'project_margin_call': False})
                continue

            bb_fac, bb_con, used_fac = self._contract_pledge_split(contract)
            fac_ids = contract.facility_ids.ids

            # ① dư nợ TẠI facility này — theo HỢP ĐỒNG nếu dòng gắn hợp
            #    đồng, ngược lại theo dự án (trừ phần các hợp đồng đã có
            #    dòng riêng, nếu không sẽ trừ hai lần).
            if rec.contract_id:
                used_p_fac = self._used_by_contract(
                    fac, {rec.contract_id.id}).get(rec.contract_id.id, 0.0)
            else:
                used_p_fac = used_fac.get((fac.id, proj.id), 0.0)
                siblings_ct = self.search([
                    ('facility_id', '=', fac.id),
                    ('project_id', '=', proj.id),
                    ('contract_id', '!=', False)]).mapped('contract_id')
                if siblings_ct:
                    taken = self._used_by_contract(fac, set(siblings_ct.ids))
                    used_p_fac = max(0.0, used_p_fac - sum(taken.values()))
            used_p_all = sum(v for (f, p), v in used_fac.items()
                             if p == proj.id)

            # ② BB dùng được cho dự án TẠI facility này:
            #    (a) TSBĐ dự án cầm cố RIÊNG facility này — ring-fence;
            #    (b) TSBĐ dự án cầm cố cấp HĐTD — bể của dự án dùng chung
            #        cho mọi facility, trừ phần các facility KHÁC đang tựa.
            bb_ring = bb_fac.get((fac.id, proj.id), 0.0)
            need_other_fac = sum(
                max(0.0, used_fac.get((f, proj.id), 0.0)
                    - bb_fac.get((f, proj.id), 0.0))
                for f in fac_ids if f != fac.id)
            pool_p = bb_con.get(proj.id, 0.0)
            pool_p_left = max(0.0, pool_p - need_other_fac)
            residual_p = max(0.0, need_other_fac - pool_p)
            bb_p = bb_ring + pool_p_left

            # bể chung (TSBĐ KHÔNG gắn dự án): phần cầm cố riêng facility
            # này + phần cầm cố cấp HĐTD; trừ đi phần các dự án khác (và nợ
            # không gắn dự án) đang tựa vào sau khi hết BB riêng của họ.
            shared_bb = bb_fac.get((fac.id, 0), 0.0) + bb_con.get(0, 0.0)
            bb_total_by, used_total_by = {}, {}
            for (f, p), v in bb_fac.items():
                bb_total_by[p] = bb_total_by.get(p, 0.0) + v
            for p, v in bb_con.items():
                bb_total_by[p] = bb_total_by.get(p, 0.0) + v
            for (f, p), v in used_fac.items():
                used_total_by[p] = used_total_by.get(p, 0.0) + v
            overflow_others = 0.0
            for pid, used in used_total_by.items():
                if pid == proj.id:
                    continue
                overflow_others += max(0.0, used - bb_total_by.get(pid, 0.0))
            shared_left = max(
                0.0, shared_bb - overflow_others - residual_p)

            # ── Công thức CHUẨN theo tài liệu nghiệp vụ §6 + ví dụ
            #    §9.7/§9.9: khả dụng của một công trình = số NHỎ NHẤT của
            #    ba giới hạn. (Bản 1.17/1.18 bỏ min() theo chỉ đạo, nhưng
            #    tài liệu khách cho kết quả ngược hẳn — anh Đại nhận sai
            #    2026-08-10, khôi phục.)
            #      ① hạn mức riêng của công trình còn lại
            #      ② TSBĐ riêng công trình (+ phần bể chung với tới được)
            #         còn gánh được — đây là nhánh hay ép về 0, và theo
            #         §9.8 thì 0 LÀ ĐÚNG, không phải lỗi
            #      ③ hạn mức thật của facility + TSBĐ chung toàn HĐTD
            has_bb = bool(bb_total_by)
            b_limit = rec.amount - used_p_fac                      # ①
            b_coll = (bb_p + shared_left - used_p_fac              # ②
                      if has_bb else None)
            b_fac = fac.amount_available                           # ③a
            b_umb = (contract.borrowing_base_total                 # ③b
                     - contract.amount_used_total
                     if contract.has_any_pledges else None)
            branches = [('limit', b_limit), ('collateral', b_coll),
                        ('facility', b_fac), ('umbrella', b_umb)]
            live = [(k, v) for k, v in branches if v is not None]
            key, val = min(live, key=lambda kv: kv[1])

            rec.amount_used_project = used_p_fac
            rec.borrowing_base_project = bb_p
            rec.shared_headroom = shared_left
            rec.amount_available_project = max(0.0, val)
            rec.blocked_by = key if val < max(
                v for _k, v in live) - 0.01 else 'none'
            # Thêm bao nhiêu nữa thì nhánh này hết chặn (§9.9: thêm IPC 80
            # tỷ × 60% = 48 tỷ BB → mở khoá đúng 48 tỷ khả dụng)
            others = [v for k, v in live if k != key]
            rec.unlock_gap = max(0.0, min(others) - val) if others else 0.0
            # Thiếu bảo đảm: xét TOÀN dự án trên HĐTD (BB mọi cấp của dự án
            # + bể chung còn trống) — cảnh báo là chuyện của cả dự án, không
            # phải của riêng một facility.
            rec.project_margin_call = bool(
                has_bb and used_p_all > bb_total_by.get(proj.id, 0.0)
                + shared_left + 0.01)


class ReLoanNoteDisbursementProjectLock(models.Model):
    """Dòng giải ngân bám DỰ ÁN CỦA KW.

    KW đã khai dự án → dòng chỉ được chọn đúng dự án đó, và tự điền sẵn.
    Kéo theo (không phải sửa gì thêm): hợp đồng nhà thầu, hạng mục, nhóm
    chi phí trên dòng vốn đã lọc theo `project_id` của dòng → nay tự động
    chỉ còn của dự án KW.
    """
    _inherit = 're.loan.note.disbursement'

    @api.depends('note_id.project_id',
                 'note_id.facility_id.project_allocation_ids.project_id')
    def _compute_allowed_project_ids(self):
        super()._compute_allowed_project_ids()
        for rec in self:
            if rec.note_id.project_id:
                rec.allowed_project_ids = rec.note_id.project_id

    @api.onchange('note_id')
    def _onchange_note_project(self):
        if self.note_id.project_id and not self.project_id:
            self.project_id = self.note_id.project_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            note = self.env['re.loan.note'].browse(vals.get('note_id'))
            if note.project_id and not vals.get('project_id'):
                vals['project_id'] = note.project_id.id
        return super().create(vals_list)

    @api.constrains('project_id', 'note_id')
    def _check_project_matches_note(self):
        for rec in self:
            note_proj = rec.note_id.project_id
            if note_proj and rec.project_id and rec.project_id != note_proj:
                raise ValidationError(_(
                    'Dòng giải ngân đang ghi dự án %(d)s trong khi KW '
                    '%(kw)s khai dự án %(n)s — phải cùng một dự án.\n'
                    '(Muốn giải ngân cho nhiều dự án: bỏ trống dự án trên '
                    'KW, hoặc lập KW riêng cho từng dự án.)',
                    d=rec.project_id.display_name, kw=rec.note_id.name,
                    n=note_proj.display_name))
