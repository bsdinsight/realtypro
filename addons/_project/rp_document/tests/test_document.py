# -*- coding: utf-8 -*-
"""Sổ hồ sơ: khoá đúng những chỗ hợp đồng dễ bị đếm sai."""
from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'rp_document')
class TestDocument(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env['re.project'].create({
            'name': 'Proj-DOC', 'code': 'DOC',
            'expected_handover_date': '2027-06-30'})
        cls.subzone = cls.env['re.subzone'].create({
            'name': 'SZ-DOC', 'project_id': cls.project.id, 'code': 'SZ'})
        cls.structure = cls.env['rp.structure'].create({
            'name': 'HM-DOC', 'project_id': cls.project.id,
            'subzone_id': cls.subzone.id,
            'structure_level': 'item', 'structure_type': 'tower'})
        cls.package = cls.env['rp.tender.package'].create({
            'name': 'GT-DOC', 'project_id': cls.project.id})
        cls.env['rp.tender.package.line'].create({
            'package_id': cls.package.id, 'structure_id': cls.structure.id})
        partner = cls.env['res.partner'].create({
            'is_contractor': True, 'is_company': True,
            'name': 'NT-DOC', 'ref': 'NT-DOC'})
        cls.contract = cls.env['rp.contract'].create({
            'name': 'HD-DOC', 'tender_package_id': cls.package.id,
            'contractor_id': partner.id,
            'contract_value_pretax': 1_000_000_000.0,
            'date_start': '2026-01-01', 'date_end': '2027-06-30'})
        cls.contract.action_sign()
        cls.sched = cls.contract._get_or_create_schedule_project()
        cls.task = cls.env['project.task'].create({
            'name': 'Đổ bê tông móng',
            'project_id': cls.sched.id,
            'rp_contract_id': cls.contract.id, 'wbs_code': '1',
            'planned_start': '2026-03-01', 'planned_end': '2026-04-30'})
        cls.Doc = cls.env['rp.document']

    def _doc(self, **kw):
        vals = {
            'name': 'Thiết kế móng', 'doc_type': 'design',
            'review_track': 'approval', 'project_id': self.project.id,
            'contract_id': self.contract.id, 'review_days': 21,
        }
        vals.update(kw)
        return self.Doc.create(vals)

    # --- Đồng hồ điều 5.2 ------------------------------------------
    def test_dong_ho_chi_chay_khi_co_ca_thong_bao(self):
        """Gửi hồ sơ mà thiếu thông báo 5.2 thì hạn CHƯA bắt đầu đếm."""
        doc = self._doc()
        doc._submit(date=fields.Date.to_date('2026-01-10'),
                    with_notice=False)
        self.assertFalse(doc.clock_start)
        self.assertFalse(doc.review_deadline)
        self.assertTrue(doc.pending_notice,
                        'Phải nói rõ là đang chờ thông báo, không phải '
                        'chờ người duyệt')

    def test_dong_ho_dem_tu_ngay_muon_hon(self):
        """Có đủ hai thứ thì đếm từ ngày muộn hơn, không phải ngày gửi."""
        doc = self._doc()
        doc.write({'state': 'submitted',
                   'date_submitted': '2026-01-10',
                   'date_notice': '2026-01-15'})
        self.assertEqual(str(doc.clock_start), '2026-01-15')
        self.assertEqual(str(doc.review_deadline), '2026-02-05')  # +21
        self.assertFalse(doc.pending_notice)

    def test_bo_sung_thong_bao_thi_dong_ho_chay(self):
        doc = self._doc()
        doc._submit(date=fields.Date.to_date('2026-01-10'),
                    with_notice=False)
        doc.action_add_notice()
        self.assertTrue(doc.review_deadline)
        self.assertEqual(doc.revision_ids[:1].date_notice, doc.date_notice)

    def test_xem_xet_tre_giu_lai_so_ngay(self):
        """Trả lời muộn rồi thì vẫn phải giữ số ngày trễ — đó là bằng chứng."""
        doc = self._doc()
        doc.write({'state': 'submitted', 'date_submitted': '2026-01-01',
                   'date_notice': '2026-01-01'})
        self.assertEqual(str(doc.review_deadline), '2026-01-22')
        doc.write({'date_reviewed': '2026-02-01'})
        self.assertEqual(doc.review_late_days, 10)
        self.assertFalse(doc.is_review_overdue,
                         'Đã trả lời thì không còn ĐANG quá hạn')

    def test_trinh_tre_so_han_phai_trinh(self):
        doc = self._doc(date_required='2026-01-01')
        doc._submit(date=fields.Date.to_date('2026-01-11'))
        self.assertEqual(doc.submit_late_days, 10)

    # --- Cổng cho phép khởi công -----------------------------------
    def test_trinh_de_duyet_chua_duyet_la_chan(self):
        doc = self._doc(review_track='approval')
        doc.task_ids = [(4, self.task.id)]
        doc._submit(date=fields.Date.to_date('2026-01-01'))
        self.task.invalidate_recordset()
        self.assertFalse(doc.gate_certain,
                         'Còn chờ người ta duyệt thì ngày mở cổng chưa chắc')
        self.assertTrue(self.task.doc_gate_blocked)

    def test_trinh_de_xem_xet_het_han_la_duoc_lam(self):
        """Điều 5.2: hồ sơ chỉ trình để xem xét thì hết hạn là được làm."""
        doc = self._doc(review_track='review')
        doc.task_ids = [(4, self.task.id)]
        doc._submit(date=fields.Date.to_date('2026-01-01'))
        self.task.invalidate_recordset()
        self.assertTrue(doc.gate_certain)
        self.assertEqual(str(doc.gate_date), '2026-01-22')
        self.assertFalse(self.task.doc_gate_blocked)
        self.assertEqual(str(self.task.doc_gate_ready_date), '2026-01-22')

    def test_duyet_roi_thi_cong_mo_tu_ngay_duyet(self):
        doc = self._doc()
        doc.task_ids = [(4, self.task.id)]
        doc._submit(date=fields.Date.to_date('2026-01-01'))
        doc.action_approve()
        self.task.invalidate_recordset()
        self.assertEqual(doc.gate_date, doc.date_reviewed)
        self.assertFalse(self.task.doc_gate_blocked)

    def test_ho_so_chi_de_biet_khong_chan(self):
        doc = self._doc(review_track='info')
        doc.task_ids = [(4, self.task.id)]
        self.task.invalidate_recordset()
        self.assertEqual(self.task.doc_gate_count, 0)
        self.assertFalse(self.task.doc_gate_blocked)

    def test_thieu_mot_cong_thi_chua_biet_ngay_khoi_cong(self):
        """Hai hồ sơ, một cái chưa trình: không được lấy ngày của cái đã biết."""
        done = self._doc(review_track='review')
        done.task_ids = [(4, self.task.id)]
        done._submit(date=fields.Date.to_date('2026-01-01'))
        self._doc(name='Biện pháp thi công').task_ids = [(4, self.task.id)]
        self.task.invalidate_recordset()
        self.assertEqual(self.task.doc_gate_count, 2)
        self.assertFalse(self.task.doc_gate_ready_date)
        self.assertTrue(self.task.doc_gate_blocked)

    def test_cho_ho_so_dem_tu_hom_nay_khi_da_qua_ngay_khoi_cong(self):
        doc = self._doc()
        doc.task_ids = [(4, self.task.id)]
        self.task.planned_start = '2020-01-01'
        self.task.invalidate_recordset()
        self.assertGreater(self.task.doc_gate_slip_days, 0)

    # --- Chuỗi lần trình -------------------------------------------
    def test_tra_lai_roi_trinh_lai_tang_rev(self):
        doc = self._doc()
        doc._submit(date=fields.Date.to_date('2026-01-01'))
        doc.action_reject()
        self.assertEqual(doc.state, 'rejected')
        self.assertEqual(doc.revision_ids[:1].outcome, 'c')
        doc.action_resubmit()
        self.assertEqual(doc.revision, 1)
        self.assertEqual(len(doc.revision_ids), 2)
        self.assertEqual(doc.state, 'submitted')

    def test_khong_trinh_de_khi_da_duyet(self):
        doc = self._doc()
        doc._submit(date=fields.Date.to_date('2026-01-01'))
        doc.action_approve()
        with self.assertRaises(UserError):
            doc._submit()

    # --- Phiếu chuyển ----------------------------------------------
    def test_phieu_chuyen_ghi_ca_lo_cung_mot_ngay(self):
        docs = self._doc() | self._doc(name='Tính toán móng',
                                       doc_type='calculation')
        tm = self.env['rp.transmittal'].create({
            'name': 'Công văn 12 bản vẽ',
            'project_id': self.project.id,
            'contract_id': self.contract.id,
            'date': '2026-02-01', 'with_notice': True,
            'document_ids': [(6, 0, docs.ids)]})
        tm.action_register()
        self.assertEqual(tm.state, 'registered')
        for doc in docs:
            self.assertEqual(doc.state, 'submitted')
            self.assertEqual(str(doc.clock_start), '2026-02-01')
            self.assertEqual(str(doc.review_deadline), '2026-02-22')
            self.assertEqual(doc.revision_ids[:1].transmittal_id, tm)

    def test_phieu_chuyen_khong_kem_thong_bao(self):
        doc = self._doc()
        tm = self.env['rp.transmittal'].create({
            'name': 'Gửi bản vẽ, chưa có thông báo',
            'project_id': self.project.id, 'date': '2026-02-01',
            'with_notice': False, 'document_ids': [(6, 0, doc.ids)]})
        tm.action_register()
        self.assertFalse(doc.review_deadline)
        self.assertTrue(doc.pending_notice)

    # --- Cổng bàn giao (5.6 / 5.7) ---------------------------------
    def test_thieu_hoan_cong_thi_chua_du_de_ban_giao(self):
        asbuilt = self._doc(name='Hồ sơ hoàn công', doc_type='as_built',
                            review_track='review', is_toc_required=True)
        self.contract.invalidate_recordset()
        self.assertEqual(self.contract.doc_toc_outstanding_count, 1)
        self.assertFalse(self.contract.toc_doc_ready)
        asbuilt._submit(date=fields.Date.to_date('2026-01-01'))
        asbuilt.action_approve()
        self.contract.invalidate_recordset()
        self.assertEqual(self.contract.doc_toc_outstanding_count, 0)
        self.assertTrue(self.contract.toc_doc_ready)

    # --- Ra khiếu nại ----------------------------------------------
    def test_qua_han_xem_xet_ra_khieu_nai_dung_so_ngay(self):
        doc = self._doc()
        doc.task_ids = [(4, self.task.id)]
        doc.write({'state': 'submitted', 'date_submitted': '2026-01-01',
                   'date_notice': '2026-01-01',
                   'date_reviewed': '2026-02-01'})
        doc.action_create_review_claim()
        claim = doc.claim_id
        self.assertTrue(claim)
        self.assertEqual(claim.eot_days_claimed, 10)
        self.assertEqual(claim.cause, 'approval')
        self.assertEqual(claim.direction, 'from_contractor')
        self.assertIn(self.task, claim.task_ids)

    def test_con_trong_han_thi_khong_cho_mo_khieu_nai(self):
        doc = self._doc()
        doc._submit(date=fields.Date.context_today(self.Doc))
        with self.assertRaises(UserError):
            doc.action_create_review_claim()

    # --- Bộ hồ sơ khởi tạo -----------------------------------------
    def test_bo_ho_so_khoi_tao_khong_tao_trung(self):
        self.contract.action_seed_document_register()
        first = self.contract.document_count
        self.assertGreater(first, 10)
        self.contract.action_seed_document_register()
        self.contract.invalidate_recordset()
        self.assertEqual(self.contract.document_count, first)
        toc = self.contract.document_ids.filtered('is_toc_required')
        self.assertEqual(len(toc), 2, 'Hoàn công và vận hành — hai hồ sơ '
                                      'chặn bàn giao')
