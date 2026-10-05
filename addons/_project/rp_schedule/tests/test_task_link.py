# -*- coding: utf-8 -*-
"""Quan hệ trước–sau có loại và độ lệch: SS/FF/SF + lag.

Bài kiểm quan trọng nhất không phải "có lưu được SS không", mà là **dư
địa có thay đổi đúng không**. Một quan hệ SS+lag nới hoặc siết dư địa
khác hẳn FS, và nếu backward pass tính sai thì đường găng chỉ sai một
cách im lặng — không ai thấy, cho tới lúc trễ dự án.
"""
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'rp_schedule')
class TestTaskLink(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env['re.project'].create({
            'name': 'Proj-LNK', 'code': 'LNK',
            'expected_handover_date': '2026-12-31'})
        cls.subzone = cls.env['re.subzone'].create({
            'name': 'SZ-LNK', 'project_id': cls.project.id, 'code': 'SZ'})
        cls.structure = cls.env['rp.structure'].create({
            'name': 'HM-LNK', 'project_id': cls.project.id,
            'subzone_id': cls.subzone.id,
            'structure_level': 'item', 'structure_type': 'tower'})
        cls.package = cls.env['rp.tender.package'].create({
            'name': 'GT-LNK', 'project_id': cls.project.id})
        cls.env['rp.tender.package.line'].create({
            'package_id': cls.package.id, 'structure_id': cls.structure.id})
        contractor = cls.env['res.partner'].create({
            'is_contractor': True, 'is_company': True,
            'name': 'NT-LNK', 'ref': 'NT-LNK'})
        cls.contract = cls.env['rp.contract'].create({
            'name': 'HD-LNK', 'tender_package_id': cls.package.id,
            'contractor_id': contractor.id,
            'contract_value_pretax': 1_000_000_000.0,
            'date_end': '2026-12-31'})
        cls.contract.action_sign()
        cls.sched = cls.contract._get_or_create_schedule_project()
        cls.Link = cls.env['rp.task.link']
        cls.Task = cls.env['project.task']

    def _task(self, wbs, name, start, end):
        return self.Task.create({
            'name': name, 'project_id': self.sched.id,
            'rp_contract_id': self.contract.id, 'wbs_code': wbs or False,
            'planned_start': start, 'planned_end': end})

    # --- Đánh số công việc ----------------------------------------
    def test_viec_moi_tu_nhan_so_ke_tiep(self):
        a = self._task('1', 'Việc đầu', '2026-01-01', '2026-01-10')
        b = self._task('2', 'Việc hai', '2026-01-11', '2026-01-20')
        c = self._task('3', 'Việc ba', '2026-01-21', '2026-01-30')
        self.assertEqual([a.wbs_seq, b.wbs_seq, c.wbs_seq], [1, 2, 3])

    def test_so_da_cap_khong_bao_gio_doi(self):
        """Chèn việc vào giữa KHÔNG được làm việc sau đó chạy số.

        Người dùng ghi "việc số 2" ra biên bản thì tuần sau vẫn phải là
        đúng việc đó — đây là lý do không đánh số lại cả loạt.
        """
        a = self._task('1', 'Việc đầu', '2026-01-01', '2026-01-10')
        b = self._task('3', 'Việc ba', '2026-01-21', '2026-01-30')
        chen = self._task('2', 'Chèn vào giữa', '2026-01-11', '2026-01-20')
        a.invalidate_recordset()
        b.invalidate_recordset()
        self.assertEqual([a.wbs_seq, b.wbs_seq], [1, 2])
        self.assertEqual(chen.wbs_seq, 3, 'Việc chèn lấy số kế tiếp, '
                                          'không chen vào giữa dãy số')

    def test_cap_so_cho_viec_chua_co(self):
        a = self._task('1', 'Có số', '2026-01-01', '2026-01-10')
        b = self._task('2', 'Chưa số', '2026-01-11', '2026-01-20')
        b.wbs_seq = 0
        n = self.Task.rp_fill_missing_seq(contract_id=self.contract.id)
        a.invalidate_recordset()
        b.invalidate_recordset()
        self.assertEqual(n, 1)
        self.assertEqual(a.wbs_seq, 1, 'Việc đã có số không bị đụng')
        self.assertEqual(b.wbs_seq, 2)
        self.assertEqual(
            self.Task.rp_fill_missing_seq(contract_id=self.contract.id), 0)

    def test_cap_wbs_tu_dem_dau_cham(self):
        a = self._task('7', 'Cấp 1', '2026-01-01', '2026-01-10')
        b = self._task('7.2', 'Cấp 2', '2026-01-01', '2026-01-05')
        c = self._task('7.2.4', 'Cấp 3', '2026-01-01', '2026-01-03')
        self.assertEqual([a.wbs_level, b.wbs_level, c.wbs_level], [1, 2, 3])
        d = self._task(False, 'Không mã', '2026-01-01', '2026-01-02')
        self.assertEqual(d.wbs_level, 0)

    # --- Độ lệch thực tế đo theo đúng loại quan hệ -----------------
    def test_lech_thuc_te_tung_loai(self):
        a = self._task('1', 'Trước', '2026-01-01', '2026-01-10')
        b = self._task('2', 'Sau', '2026-01-06', '2026-01-20')
        ln = self.Link.create({'task_id': b.id, 'predecessor_id': a.id})
        # FS: b bắt đầu 06/01, a xong 10/01 → chồng lấn 5 ngày
        self.assertEqual(ln.lag_actual, -5)
        self.assertTrue(ln.is_violated, 'FS mà chồng lấn là vi phạm')
        ln.link_type = 'SS'
        self.assertEqual(ln.lag_actual, 5)      # 01/01 → 06/01
        ln.link_type = 'FF'
        self.assertEqual(ln.lag_actual, 10)     # 10/01 → 20/01
        ln.link_type = 'SF'
        self.assertEqual(ln.lag_actual, 19)     # 01/01 → 20/01

    def test_khai_dung_lag_thi_khong_con_vi_pham(self):
        a = self._task('1', 'Trước', '2026-01-01', '2026-01-10')
        b = self._task('2', 'Sau', '2026-01-06', '2026-01-20')
        ln = self.Link.create({'task_id': b.id, 'predecessor_id': a.id,
                               'link_type': 'SS', 'lag_days': 5})
        self.assertEqual(ln.lag_gap, 0)
        self.assertFalse(ln.is_violated)
        # Việc sau nhích sớm hơn mức SS+5 cho phép → vi phạm
        b.planned_start = '2026-01-03'
        self.assertTrue(ln.is_violated)
        self.assertEqual(ln.lag_gap, -3)

    def test_khong_tu_tro_va_khong_trung_loai(self):
        a = self._task('1', 'Trước', '2026-01-01', '2026-01-10')
        b = self._task('2', 'Sau', '2026-01-11', '2026-01-20')
        with self.assertRaises(ValidationError):
            self.Link.create({'task_id': a.id, 'predecessor_id': a.id})
        self.Link.create({'task_id': b.id, 'predecessor_id': a.id})
        # Loại khác cho cùng cặp thì ĐƯỢC — ghép SS với FF là cách chuẩn
        # mô tả hai tổ đi nối đuôi nhau.
        self.Link.create({'task_id': b.id, 'predecessor_id': a.id,
                          'link_type': 'SS'})
        with self.assertRaises(ValidationError):
            self.Link.create({'task_id': b.id, 'predecessor_id': a.id,
                              'link_type': 'FS', 'lag_days': 3})

    def test_cap_ss_ff_truyen_ca_vo_thoi_luong(self):
        """Vì sao SS một mình là chưa đủ.

        SS neo hai NGÀY BẮT ĐẦU. Việc trước giữ nguyên ngày bắt đầu mà
        làm lâu thêm 45 ngày thì SS không đòi việc sau nhúc nhích — chậm
        không tới được mốc. Thêm nhánh FF thì truyền.
        """
        a = self._task('1', 'Làm đường batch 1', '2026-01-01', '2026-02-10')
        b = self._task('2', 'Đổ móng batch 1', '2026-01-26', '2026-03-10')
        ss = self.Link.create({'task_id': b.id, 'predecessor_id': a.id})
        ss.action_set_ss_from_dates()
        self.assertEqual(ss.link_type, 'SS')
        self.assertEqual(ss.lag_days, 25)
        ff = self.Link.search([('task_id', '=', b.id),
                               ('link_type', '=', 'FF')])
        self.assertTrue(ff, 'Phải tự thêm nhánh FF đi kèm')
        self.assertEqual(ff.lag_days, 28)
        self.assertFalse(ss.is_violated)
        self.assertFalse(ff.is_violated)
        # Giữ ngày bắt đầu, kéo dài 45 ngày → việc sau phải dời theo FF.
        a.rp_shift_schedule('2026-01-01', '2026-03-27')
        b.invalidate_recordset()
        self.assertEqual(str(b.planned_start), '2026-03-12',
                         'Nhánh FF đẩy việc sau đi, SS một mình thì không')

    def test_ff_khong_them_khi_viec_sau_xong_truoc(self):
        """Không bịa quan hệ: việc sau xong TRƯỚC thì FF vô nghĩa."""
        a = self._task('1', 'Trước', '2026-01-01', '2026-03-31')
        b = self._task('2', 'Sau ngắn', '2026-01-10', '2026-01-20')
        ln = self.Link.create({'task_id': b.id, 'predecessor_id': a.id})
        added = ln.action_set_ss_from_dates()
        self.assertFalse(added)
        self.assertFalse(self.Link.search_count([
            ('task_id', '=', b.id), ('link_type', '=', 'FF')]))

    # --- Lối vào đơn giản vẫn chạy ---------------------------------
    def test_predecessor_ids_doc_ghi_loc(self):
        a = self._task('1', 'Trước', '2026-01-01', '2026-01-10')
        b = self._task('2', 'Sau', '2026-01-11', '2026-01-20')
        b.predecessor_ids = [(6, 0, a.ids)]
        self.assertEqual(len(b.link_ids), 1)
        self.assertEqual(b.link_ids.link_type, 'FS')
        self.assertEqual(b.predecessor_ids, a)
        # Lọc theo predecessor_ids phải ra việc sau
        found = self.Task.search([('predecessor_ids', 'in', a.ids),
                                  ('rp_contract_id', '=', self.contract.id)])
        self.assertIn(b, found)
        b.predecessor_ids = [(6, 0, [])]
        self.assertFalse(b.link_ids)

    def test_ghi_loi_vao_don_gian_khong_de_len_loai_rieng(self):
        """Ghi bằng predecessor_ids không được biến SS+20 thành FS+0."""
        a = self._task('1', 'Trước', '2026-01-01', '2026-01-30')
        b = self._task('2', 'Sau', '2026-01-21', '2026-02-10')
        c = self._task('3', 'Sau nữa', '2026-02-11', '2026-02-20')
        self.Link.create({'task_id': b.id, 'predecessor_id': a.id,
                          'link_type': 'SS', 'lag_days': 20})
        b.predecessor_ids = [(6, 0, (a | c).ids)]
        keep = b.link_ids.filtered(lambda l: l.predecessor_id == a)
        self.assertEqual(keep.link_type, 'SS')
        self.assertEqual(keep.lag_days, 20)

    # --- Dư địa: SS+lag cho số KHÁC FS -----------------------------
    def test_ss_lag_cho_du_dia_khac_fs(self):
        """Hai việc chồng lấn: FS thì sai, SS+lag mới ra dư địa đúng.

        A 01→30/01 (dur 29), B 21/01→10/02. Mốc xa nhất của tập là
        10/02, nên:
        * SS+20: A chỉ cần bắt đầu không muộn hơn LS(B) − 20. B không có
          việc sau nên LF(B) = 10/02 ⇒ LS(B) = 21/01, vậy A được phép
          bắt đầu tới 01/01 → dư địa 0, A nằm trên đường găng.
        * FS: A phải xong trước 21/01 trong khi A xong 30/01 ⇒ dư địa âm,
          dù lịch thực tế hoàn toàn hợp lý.
        """
        a = self._task('1', 'Đổ móng batch 1', '2026-01-01', '2026-01-30')
        b = self._task('2', 'Làm đường batch 2', '2026-01-21', '2026-02-10')
        ln = self.Link.create({'task_id': b.id, 'predecessor_id': a.id,
                               'link_type': 'SS', 'lag_days': 20})
        res = self.Task.rp_compute_critical_path(self.contract.id)
        self.assertEqual(res[a.id]['tf'], 0)
        self.assertTrue(res[a.id]['critical'])
        self.assertFalse(ln.is_violated)
        # Cùng bộ ngày, khai FS: dư địa tụt xuống âm
        ln.write({'link_type': 'FS', 'lag_days': 0})
        res_fs = self.Task.rp_compute_critical_path(self.contract.id)
        self.assertLess(res_fs[a.id]['tf'], 0)
        self.assertTrue(ln.is_violated)

    def test_ss_lag_cang_lon_cang_siet_viec_truoc(self):
        """Hướng của lag: lag LỚN hơn siết việc trước, không phải nới ra.

        SS+lag đọc là "việc sau vào sau việc trước ít nhất lag ngày". Đòi
        giãn cách lớn hơn thì việc trước phải vào SỚM hơn, nên mất dư địa.
        Nhầm hướng này là nhầm cả đường găng, nên khoá lại bằng số cụ thể:
        A 11→30/01, B 21/01→10/02, giãn cách thực tế là 10 ngày.
        """
        a = self._task('1', 'Trước', '2026-01-11', '2026-01-30')
        b = self._task('2', 'Sau', '2026-01-21', '2026-02-10')
        ln = self.Link.create({'task_id': b.id, 'predecessor_id': a.id,
                               'link_type': 'SS', 'lag_days': 10})
        tf = self.Task.rp_compute_critical_path(self.contract.id)
        self.assertEqual(tf[a.id]['tf'], 0, 'Khai đúng giãn cách → vừa khít')
        ln.lag_days = 5                      # đòi ít giãn cách hơn
        tf5 = self.Task.rp_compute_critical_path(self.contract.id)
        self.assertEqual(tf5[a.id]['tf'], 5, 'Nới giãn cách → thêm dư địa')
        self.assertFalse(ln.is_violated, 'Vào muộn hơn mức tối thiểu là hợp lệ')
        ln.lag_days = 15                     # đòi giãn cách lớn hơn
        tf15 = self.Task.rp_compute_critical_path(self.contract.id)
        self.assertEqual(tf15[a.id]['tf'], -5, 'Siết giãn cách → dư địa âm')
        self.assertTrue(ln.is_violated,
                        'Ngày đang lập chỉ cho 10 ngày, khai 15 là vi phạm')

    def test_ff_lag_chan_ngay_ket_thuc(self):
        """FF: việc trước phải xong trước khi việc sau xong, lệch lag."""
        a = self._task('1', 'Kéo dây', '2026-01-01', '2026-01-20')
        b = self._task('2', 'Thí nghiệm', '2026-01-10', '2026-01-30')
        self.Link.create({'task_id': b.id, 'predecessor_id': a.id,
                          'link_type': 'FF', 'lag_days': 10})
        res = self.Task.rp_compute_critical_path(self.contract.id)
        # LF(B) = 30/01 (không có việc sau) ⇒ LF(A) ≤ 30/01 − 10 = 20/01
        # A xong 20/01 ⇒ dư địa 0.
        self.assertEqual(res[a.id]['tf'], 0)

    def test_fs_co_lag_cho_doi_khoang_cho(self):
        """FS+5: việc sau phải chờ thêm 5 ngày, việc trước mất 5 ngày dư."""
        a = self._task('1', 'Đổ bê tông', '2026-01-01', '2026-01-10')
        b = self._task('2', 'Tháo coppha', '2026-01-16', '2026-01-25')
        ln = self.Link.create({'task_id': b.id, 'predecessor_id': a.id,
                               'link_type': 'FS', 'lag_days': 5})
        self.assertEqual(ln.lag_actual, 5)
        self.assertFalse(ln.is_violated)
        res = self.Task.rp_compute_critical_path(self.contract.id)
        self.assertEqual(res[a.id]['tf'], 0)
        ln.lag_days = 0                      # bỏ thời gian bảo dưỡng
        res0 = self.Task.rp_compute_critical_path(self.contract.id)
        self.assertEqual(res0[a.id]['tf'], 5)

    def test_ss_khong_cho_lf_vuot_ngay_ve_dich(self):
        """Quan hệ SS không chặn ngày kết thúc — phải có chặn trên.

        A dài, chỉ có một quan hệ SS tới B ngắn. Nếu không chặn bằng ngày
        về đích của tập thì LF(A) chạy quá xa và dư địa dương vô lý.
        """
        a = self._task('1', 'Việc dài', '2026-01-01', '2026-03-31')
        b = self._task('2', 'Việc ngắn', '2026-01-05', '2026-01-10')
        self.Link.create({'task_id': b.id, 'predecessor_id': a.id,
                          'link_type': 'SS', 'lag_days': 4})
        res = self.Task.rp_compute_critical_path(self.contract.id)
        self.assertEqual(res[a.id]['tf'], 0,
                         'Việc kết thúc muộn nhất của tập luôn có dư địa 0')

    # --- Dọn mạng phụ thuộc theo lô --------------------------------
    def test_chuyen_ca_loat_fs_chong_lan_sang_ss(self):
        a = self._task('1', 'Trước', '2026-01-01', '2026-01-30')
        b = self._task('2', 'Sau', '2026-01-21', '2026-02-10')
        c = self._task('3', 'Sau nữa', '2026-02-01', '2026-02-20')
        self.Link.create({'task_id': b.id, 'predecessor_id': a.id})
        self.Link.create({'task_id': c.id, 'predecessor_id': b.id})
        self.assertEqual(self.project.schedule_link_violated_count, 2)
        self.project.action_links_to_ss()
        self.project.invalidate_recordset()
        self.assertEqual(self.project.schedule_link_violated_count, 0)
        # Mỗi cặp chồng lấn ra một SS + một FF ⇒ 2 cặp thành 4 quan hệ.
        self.assertEqual(self.project.schedule_link_count, 4)
        self.assertEqual(self.project.schedule_link_ss_count, 4)
        ss = self.Link.search([('task_id', '=', b.id),
                               ('link_type', '=', 'SS')])
        self.assertEqual(ss.lag_days, 20)
        ff = self.Link.search([('task_id', '=', b.id),
                               ('link_type', '=', 'FF')])
        self.assertEqual(ff.lag_days, 11)

    def test_keo_thanh_ss_di_theo_ngay_bat_dau(self):
        """Kéo việc trước: SS theo delta NGÀY BẮT ĐẦU, FS theo kết thúc."""
        a = self._task('1', 'Trước', '2026-01-01', '2026-01-30')
        b = self._task('2', 'Sau SS', '2026-01-21', '2026-02-10')
        c = self._task('3', 'Sau FS', '2026-02-11', '2026-02-20')
        self.Link.create({'task_id': b.id, 'predecessor_id': a.id,
                          'link_type': 'SS', 'lag_days': 20})
        self.Link.create({'task_id': c.id, 'predecessor_id': a.id})
        # Giữ ngày bắt đầu, kéo dài thêm 10 ngày: SS không dời, FS dời 10.
        a.rp_shift_schedule('2026-01-01', '2026-02-09')
        b.invalidate_recordset()
        c.invalidate_recordset()
        self.assertEqual(str(b.planned_start), '2026-01-21')
        self.assertEqual(str(c.planned_start), '2026-02-21')
