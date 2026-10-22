# -*- coding: utf-8 -*-
"""Thư viện điều khoản FIDIC — kiến thức của BSD, không chép của ai.

Vì sao là thư viện chứ không phải dữ liệu của một khách
--------------------------------------------------------
Rút số trang và trích đoạn từ hợp đồng của một khách thì được một bản
demo đẹp cho đúng khách đó, và không dùng lại được cho ai. Tệ hơn: hợp
đồng EPC thường đóng dấu *Commercial in Confidence*, nên chép nguyên văn
vào sản phẩm là việc không nên làm nhẹ tay.

Thư viện này viết từ **bộ điều kiện hợp đồng FIDIC** — chuẩn ngành công
khai, cùng một bộ số điều mà hầu hết hợp đồng EPC điện gió/mặt trời ở
Đông Nam Á đang dùng. Mỗi dòng là *số điều · nghĩa vụ nó sinh ra · bên
nào gánh · bao nhiêu ngày*, viết bằng lời của mình. Khách nào cũng áp
được, rồi sửa lại theo Điều kiện Riêng của họ.

Giới hạn phải nói trước
------------------------
**Đây là Điều kiện Chung. Điều kiện Riêng của từng hợp đồng gần như luôn
sửa một vài con số** — đó là chỗ các bên mặc cả thật. Nên mọi dòng sinh
ra từ thư viện này đều mang nhãn *"mẫu — chưa đối chiếu hợp đồng"*, và
nhãn đó chỉ nên gỡ khi có người cầm bản giấy soát lại.

Số ngày ở đây theo FIDIC 1999 (Yellow/Silver Book). Bản 2017 đổi một số
chỗ — đáng kể nhất là cơ chế khiếu nại tách Điều 20 thành 20.1/20.2 và
thêm bước của Engineer. Chưa đưa bản 2017 vào vì chưa có khách nào dùng;
thêm sau thì chỉ là một bộ dữ liệu thứ hai, không phải sửa kiến trúc.

Mốc khởi đồng hồ
-----------------
``moc`` nói đồng hồ chạy từ đâu. Phần mềm **chưa tự suy ra** được hầu
hết các mốc này — chúng nằm ở chứng từ ngoài (Thư chấp thuận, Giấy chứng
nhận nghiệm thu). Ghi ra để người dùng biết phải điền ngày nào, thay vì
để một ô ngày trống không ai hiểu dùng làm gì.
"""

#: Mốc khởi đồng hồ, dùng cho phần mô tả.
MOC = {
    'thu_chap_thuan': 'Thư chấp thuận',
    'khoi_cong': 'Ngày khởi công',
    'nhan_ho_so': 'Ngày nhận hồ sơ + thông báo',
    'su_kien': 'Ngày xảy ra sự việc',
    'chi_thi': 'Ngày có chỉ thị thay đổi',
    'yeu_cau': 'Ngày được yêu cầu',
    'cuoi_ky': 'Ngày cuối kỳ',
    'nhan_phieu': 'Ngày nhận phiếu giá',
    'het_bao_hanh': 'Ngày hết thời hạn thông báo khuyết tật',
    'nhan_chung_chi': 'Ngày nhận Chứng chỉ thực hiện',
}

#: Thư viện. Mỗi dòng:
#:   so        — số điều trong Điều kiện Chung FIDIC
#:   ten       — tên điều (giữ tên tiếng Anh để dò bản giấy) + nghĩa tiếng Việt
#:   ngay      — số ngày Điều kiện Chung quy định (0 = không đặt hạn cứng)
#:   moc       — đồng hồ chạy từ mốc nào
#:   loai/ben  — nghĩa vụ nó sinh ra thuộc loại gì, bên nào gánh
#:   sinh      — có dựng sẵn một dòng nghĩa vụ đứng sẵn không
#:   chu_ky    — nghĩa vụ lặp lại thì ghi chu kỳ
#:   mo_ta     — nghĩa vụ nói bằng lời của mình, không chép điều khoản
#:   tao_dieu  — có dựng thành một dòng điều khoản không. Để False cho
#:               những kỳ hạn là KỲ HẠN THỨ HAI trong cùng một điều:
#:               chúng là kiến thức thật, nhưng dựng thành dòng riêng
#:               thì người cầm bản giấy dò không ra số điều đó.
THU_VIEN_FIDIC = [
    # ---- Bảo lãnh & bảo đảm ------------------------------------------
    dict(so='4.2', ten="Performance Security — bảo lãnh thực hiện",
         ngay=28, moc='thu_chap_thuan', loai='bao_lanh', ben='nha_thau',
         sinh=True, chu_ky=None,
         mo_ta='Nhà thầu nộp bảo lãnh thực hiện và giữ hiệu lực cho tới '
               'khi được cấp Chứng chỉ thực hiện. Bảo lãnh sắp hết hạn mà '
               'công trình chưa xong thì phải gia hạn.'),
    dict(so='14.2', ten='Advance Payment — bảo lãnh tạm ứng',
         ngay=0, moc='thu_chap_thuan', loai='bao_lanh', ben='nha_thau',
         sinh=True, chu_ky=None,
         mo_ta='Bảo lãnh tạm ứng phải còn hiệu lực tới khi hoàn ứng hết. '
               'Giá trị giảm dần theo tiến độ thu hồi tạm ứng.'),

    # ---- Hồ sơ nhà thầu phải trình -----------------------------------
    dict(so='5.2', ten="Contractor's Documents — hồ sơ Nhà thầu trình",
         ngay=21, moc='nhan_ho_so', loai='xem_xet', ben='chu_dau_tu',
         sinh=False, chu_ky=None,
         mo_ta='Bên xem xét phải trả lời trong 21 ngày. Đồng hồ chỉ chạy '
               'khi có ĐỦ hồ sơ VÀ thông báo của nhà thầu — thiếu một '
               'trong hai thì chưa ai bị tính giờ.'),
    dict(so='4.9', ten='Quality Assurance — hệ thống quản lý chất lượng',
         ngay=0, moc='khoi_cong', loai='ho_so', ben='nha_thau',
         sinh=True, chu_ky=None,
         mo_ta='Nhà thầu trình hệ thống bảo đảm chất lượng trước khi bắt '
               'đầu từng giai đoạn thi công.'),
    dict(so='5.6', ten='As-Built Documents — hồ sơ hoàn công',
         ngay=0, moc='khoi_cong', loai='ho_so', ben='nha_thau',
         sinh=True, chu_ky=None,
         mo_ta='Hồ sơ hoàn công phải nộp trước khi nghiệm thu bàn giao — '
               'là một trong các cửa chặn của Chứng chỉ nghiệm thu.'),
    dict(so='5.7', ten='Operation and Maintenance Manuals — tài liệu O&M',
         ngay=0, moc='khoi_cong', loai='ho_so', ben='nha_thau',
         sinh=True, chu_ky=None,
         mo_ta='Tài liệu vận hành và bảo trì phải đủ trước khi chạy thử '
               'nghiệm thu. Thiếu nó thì không bàn giao sang vận hành '
               'được.'),

    # ---- Tiến độ & báo cáo -------------------------------------------
    dict(so='8.3', ten='Programme — tiến độ thi công chi tiết',
         ngay=28, moc='khoi_cong', loai='ho_so', ben='nha_thau',
         sinh=True, chu_ky=None,
         mo_ta='Nhà thầu nộp tiến độ chi tiết trong 28 ngày kể từ ngày '
               'khởi công, và nộp lại mỗi khi tiến độ thực tế không còn '
               'khớp.'),
    dict(so='4.21', ten='Progress Reports — báo cáo tiến độ',
         ngay=7, moc='cuoi_ky', loai='bao_cao', ben='nha_thau',
         sinh=True, chu_ky='thang',
         mo_ta='Báo cáo tiến độ hàng tháng, nộp trong 7 ngày sau khi hết '
               'kỳ. Đây là nghĩa vụ lặp nên mỗi tháng là một hạn riêng.'),

    # ---- Bảo hiểm -----------------------------------------------------
    dict(so='18.1', ten='General Requirements for Insurances — bằng chứng bảo hiểm',
         ngay=28, moc='thu_chap_thuan', loai='bao_hiem', ben='nha_thau',
         sinh=True, chu_ky=None,
         mo_ta='Nộp bằng chứng bảo hiểm và bản sao đơn bảo hiểm. Đơn hết '
               'hạn giữa kỳ thi công mà không gia hạn là vi phạm, và là '
               'rủi ro thật chứ không phải thủ tục.'),
    dict(so='18.2', ten="Insurance for Works and Contractor's Equipment — bảo hiểm công trình",
         ngay=0, moc='khoi_cong', loai='bao_hiem', ben='nha_thau',
         sinh=True, chu_ky=None,
         mo_ta='Bảo hiểm mọi rủi ro xây dựng cho công trình và thiết bị '
               'thi công, hiệu lực từ khởi công tới khi hết trách nhiệm '
               'khuyết tật.'),
    dict(so='18.3', ten='Insurance against Injury to Persons — bảo hiểm trách nhiệm bên thứ ba',
         ngay=0, moc='khoi_cong', loai='bao_hiem', ben='nha_thau',
         sinh=True, chu_ky=None,
         mo_ta='Bảo hiểm thiệt hại người và tài sản bên thứ ba.'),
    dict(so='18.4', ten="Insurance for Contractor's Personnel — bảo hiểm nhân sự",
         ngay=0, moc='khoi_cong', loai='bao_hiem', ben='nha_thau',
         sinh=True, chu_ky=None,
         mo_ta='Bảo hiểm cho người lao động của nhà thầu và nhà thầu phụ.'),

    # ---- Giấy phép ----------------------------------------------------
    dict(so='1.13', ten='Compliance with Laws — giấy phép và chấp thuận',
         ngay=0, moc='khoi_cong', loai='giay_phep', ben='hai_ben',
         sinh=True, chu_ky=None,
         mo_ta='Mỗi bên xin và duy trì những giấy phép thuộc phần mình. '
               'Giấy phép có hạn thì hết hạn giữa kỳ là dừng thi công, '
               'nên theo dõi hạn chứ không chỉ lưu bản scan.'),

    # ---- Thay đổi -----------------------------------------------------
    dict(so='13.1', ten='Right to Vary — phản đối chỉ thị thay đổi',
         ngay=14, moc='chi_thi', loai='phat_sinh', ben='nha_thau',
         sinh=False, chu_ky=None,
         mo_ta='Nhà thầu chỉ được phản đối trong 14 ngày và chỉ với các lý '
               'do hợp đồng liệt kê. Quá hạn là phải thực hiện.'),
    dict(so='13.3', ten='Variation Procedure — nộp báo giá thay đổi',
         ngay=14, moc='yeu_cau', loai='phat_sinh', ben='nha_thau',
         sinh=False, chu_ky=None,
         mo_ta='Được yêu cầu đề xuất thì nhà thầu trả lời trong 14 ngày — '
               'hoặc báo giá, hoặc nêu lý do không làm được.'),

    # ---- Khiếu nại ----------------------------------------------------
    dict(so='20.1', ten="Contractor's Claims — thông báo khiếu nại",
         ngay=28, moc='su_kien', loai='khieu_nai', ben='nha_thau',
         sinh=False, chu_ky=None,
         mo_ta='Thông báo trong 28 ngày kể từ khi biết hoặc đáng lẽ phải '
               'biết sự việc. Quá hạn là MẤT QUYỀN — đây là hạn đắt nhất '
               'trong cả hợp đồng.'),
    dict(so='20.1b', ten="Contractor's Claims — hồ sơ khiếu nại đầy đủ",
         ngay=42, moc='su_kien', loai='khieu_nai', ben='nha_thau',
         sinh=False, chu_ky=None, tao_dieu=False,
         mo_ta='Sau thông báo 28 ngày còn một hạn thứ hai: nộp hồ sơ đầy '
               'đủ kèm căn cứ trong 42 ngày. Thông báo đúng hạn mà hồ sơ '
               'trễ thì khiếu nại vẫn yếu đi.'),
    dict(so='2.5', ten="Employer's Claims — chủ đầu tư khiếu nại",
         ngay=0, moc='su_kien', loai='khieu_nai', ben='chu_dau_tu',
         sinh=False, chu_ky=None,
         mo_ta='Chủ đầu tư thông báo "sớm nhất có thể" — Điều kiện Chung '
               'KHÔNG đặt số ngày cứng, khác hẳn phía nhà thầu. Đây là '
               'chỗ bất đối xứng, đừng áp 28 ngày cho cả hai chiều.'),

    # ---- Nghiệm thu & bảo hành ---------------------------------------
    dict(so='9.1', ten='Tests on Completion — thông báo chạy thử nghiệm thu',
         ngay=21, moc='su_kien', loai='ho_so', ben='nha_thau',
         sinh=False, chu_ky=None,
         mo_ta='Nhà thầu báo trước ít nhất 21 ngày ngày sẵn sàng chạy thử '
               'nghiệm thu.'),
    dict(so='10.1', ten='Taking Over of the Works — xin nghiệm thu bàn giao',
         ngay=14, moc='su_kien', loai='ho_so', ben='nha_thau',
         sinh=False, chu_ky=None,
         mo_ta='Đơn xin nghiệm thu nộp không sớm hơn 14 ngày trước ngày dự '
               'kiến công trình hoàn thành.'),
    dict(so='11.9', ten='Performance Certificate — cấp chứng chỉ thực hiện',
         ngay=28, moc='het_bao_hanh', loai='ho_so', ben='chu_dau_tu',
         sinh=False, chu_ky=None,
         mo_ta='Chủ đầu tư cấp Chứng chỉ thực hiện trong 28 ngày sau khi '
               'hết thời hạn thông báo khuyết tật. Đây cũng là mốc giải '
               'phóng bảo lãnh thực hiện.'),

    # ---- Thanh toán ---------------------------------------------------
    dict(so='14.3', ten='Application for Interim Payment — hồ sơ thanh toán kỳ',
         ngay=0, moc='cuoi_ky', loai='ho_so', ben='nha_thau',
         sinh=True, chu_ky='thang',
         mo_ta='Nhà thầu nộp hồ sơ thanh toán hàng tháng. Nộp trễ là lùi '
               'cả chuỗi phía sau, vì mọi mốc thanh toán đếm từ ngày nhận '
               'hồ sơ.'),
    dict(so='14.6', ten='Issue of Interim Payment Certificate — cấp phiếu giá',
         ngay=28, moc='nhan_phieu', loai='ho_so', ben='chu_dau_tu',
         sinh=False, chu_ky=None,
         mo_ta='Bên xem xét cấp phiếu giá trong 28 ngày kể từ ngày nhận hồ '
               'sơ thanh toán.'),
    dict(so='14.7', ten='Payment — thanh toán phiếu giá',
         ngay=56, moc='nhan_phieu', loai='thanh_toan', ben='chu_dau_tu',
         sinh=False, chu_ky=None,
         mo_ta='Chủ đầu tư trả trong 56 ngày kể từ ngày nhận hồ sơ thanh '
               'toán. Trả trễ thì nhà thầu được tính lãi, và sau 21 ngày '
               'thông báo thì được giãn hoặc dừng thi công (đ. 16.1).'),
    dict(so='14.11', ten='Application for Final Payment — hồ sơ quyết toán',
         ngay=56, moc='nhan_chung_chi', loai='ho_so', ben='nha_thau',
         sinh=False, chu_ky=None,
         mo_ta='Nhà thầu nộp hồ sơ quyết toán trong 56 ngày kể từ ngày '
               'nhận Chứng chỉ thực hiện.'),
    dict(so='14.13', ten='Issue of Final Payment Certificate — cấp phiếu quyết toán',
         ngay=28, moc='nhan_phieu', loai='ho_so', ben='chu_dau_tu',
         sinh=False, chu_ky=None,
         mo_ta='Cấp phiếu quyết toán trong 28 ngày kể từ ngày nhận hồ sơ '
               'quyết toán.'),

    # ---- Bất khả kháng ------------------------------------------------
    dict(so='19.2', ten='Notice of Force Majeure — thông báo bất khả kháng',
         ngay=14, moc='su_kien', loai='khieu_nai', ben='hai_ben',
         sinh=False, chu_ky=None,
         mo_ta='Bên bị ảnh hưởng thông báo trong 14 ngày kể từ khi biết sự '
               'kiện bất khả kháng. Hạn này ngắn hơn hạn khiếu nại thường '
               '(28 ngày) — dễ nhầm.'),
]

for _d in THU_VIEN_FIDIC:
    _d.setdefault('tao_dieu', True)

#: Tra nhanh theo số điều.
THEO_SO = {d['so']: d for d in THU_VIEN_FIDIC}

#: Những dòng dựng được thành điều khoản của một hợp đồng.
DIEU_DUNG_DUOC = [d for d in THU_VIEN_FIDIC if d['tao_dieu']]


def dong_ho_chuan(so_dieu, mac_dinh=0):
    """Số ngày Điều kiện Chung FIDIC quy định cho một điều."""
    d = THEO_SO.get(so_dieu)
    return d['ngay'] if d and d['ngay'] else mac_dinh
