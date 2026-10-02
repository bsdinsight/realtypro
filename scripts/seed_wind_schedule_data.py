# -*- coding: utf-8 -*-
"""Sinh lịch thi công chi tiết cho dự án điện gió 12 × 4 MW.

Bảy hợp đồng, mỗi hợp đồng một WBS nhiều cấp, ≥50 dòng. Lịch được tính
bằng forward pass trên quan hệ FS (không nhập ngày tay), nên mọi phụ
thuộc — kể cả phụ thuộc giữa hai nhà thầu khác nhau — đều nhất quán.

Hai lần tính:
  * BASELINE: kế hoạch gốc, mọi việc đúng thời lượng hợp đồng.
  * HIỆN HÀNH: cộng thêm độ trễ thực tế (nacelle lô 1 chậm 42 ngày) rồi
    để forward pass lan truyền sang các nhà thầu phía sau.

Chạy trực tiếp file này để xem lịch mà không cần Odoo.
"""
import datetime as dt

WTG = ['WTG-%02d' % i for i in range(1, 13)]
LOT1, LOT2 = WTG[:6], WTG[6:]
# 6 cụm cáp, mỗi cụm 2 tua-bin
CLUSTER = [('C%d' % (i + 1), WTG[2 * i:2 * i + 2]) for i in range(6)]

ROWS = []          # (ckey, wbs, name, dur|None, preds, milestone, extra)


def row(ckey, wbs, name, dur, preds=(), ms=False, extra=0):
    ROWS.append((ckey, wbs, name, dur, tuple(preds), ms, extra))


def grp(ckey, wbs, name):
    row(ckey, wbs, name, None)


# =====================================================================
# SUP — HĐ cung cấp tua-bin (hãng sản xuất)
# =====================================================================
grp('SUP', '1', 'Thiết kế & kỹ thuật')
row('SUP', '1.1', 'Khảo sát điều kiện gió & chốt cấu hình máy', 20)
row('SUP', '1.2', 'Tính toán tải trọng thiết kế (design loads)', 25,
    ['SUP:1.1'])
row('SUP', '1.3', 'Hồ sơ giao diện móng — tháp (tower interface)', 20,
    ['SUP:1.2'])
row('SUP', '1.4', 'Chủ đầu tư duyệt hồ sơ kỹ thuật', 15, ['SUP:1.3'])
row('SUP', '1.5', 'Chốt cấu hình kỹ thuật tua-bin', 0, ['SUP:1.4'], ms=True)
row('SUP', '1.6', 'Hồ sơ chứng chỉ & kiểm định theo IEC 61400', 12,
    ['SUP:1.4'])

grp('SUP', '2', 'Mua sắm vật tư chính')
row('SUP', '2.1', 'Đặt hàng vỏ nacelle', 30, ['SUP:1.5'])
row('SUP', '2.2', 'Đặt hàng cánh quạt (36 cánh)', 35, ['SUP:1.5'])
row('SUP', '2.3', 'Đặt hàng tháp thép (12 tháp)', 40, ['SUP:1.5'])
row('SUP', '2.4', 'Đặt hàng máy phát & hộp số', 35, ['SUP:1.5'])
row('SUP', '2.5', 'Đặt hàng hệ điều khiển & biến tần', 30, ['SUP:1.5'])
row('SUP', '2.6', 'Kiểm tra chất lượng vật tư đầu vào', 15,
    ['SUP:2.1', 'SUP:2.2', 'SUP:2.3', 'SUP:2.4', 'SUP:2.5'])

grp('SUP', '3', 'Sản xuất lô 1 (6 tua-bin)')
row('SUP', '3.1', 'Sản xuất tháp lô 1', 60, ['SUP:2.6'])
# Việc trễ gốc của cả dự án: dây chuyền nacelle chậm 42 ngày.
row('SUP', '3.2', 'Sản xuất nacelle lô 1', 70, ['SUP:2.6'], extra=42)
row('SUP', '3.3', 'Sản xuất cánh lô 1 (18 cánh)', 65, ['SUP:2.6'])
row('SUP', '3.4', 'Lắp ráp & kiểm tra nội bộ lô 1', 20,
    ['SUP:3.1', 'SUP:3.2', 'SUP:3.3'])
row('SUP', '3.5', 'Nghiệm thu tại xưởng (FAT) lô 1', 10, ['SUP:3.4'])
row('SUP', '3.6', 'FAT lô 1 đạt', 0, ['SUP:3.5'], ms=True)
row('SUP', '3.7', 'Đóng gói & xuất xưởng lô 1', 10, ['SUP:3.6'])

grp('SUP', '4', 'Sản xuất lô 2 (6 tua-bin)')
row('SUP', '4.1', 'Sản xuất tháp lô 2', 60, ['SUP:3.1'])
row('SUP', '4.2', 'Sản xuất nacelle lô 2', 70, ['SUP:3.2'])
row('SUP', '4.3', 'Sản xuất cánh lô 2 (18 cánh)', 65, ['SUP:3.3'])
row('SUP', '4.4', 'Lắp ráp & kiểm tra nội bộ lô 2', 20,
    ['SUP:4.1', 'SUP:4.2', 'SUP:4.3'])
row('SUP', '4.5', 'Nghiệm thu tại xưởng (FAT) lô 2', 10, ['SUP:4.4'])
row('SUP', '4.6', 'FAT lô 2 đạt', 0, ['SUP:4.5'], ms=True)
row('SUP', '4.7', 'Đóng gói & xuất xưởng lô 2', 10, ['SUP:4.6'])

grp('SUP', '5', 'Giao hàng')
row('SUP', '5.1', 'Hồ sơ xuất khẩu lô 1', 8, ['SUP:3.7'])
row('SUP', '5.2', 'Giao hàng tại cảng xuất lô 1 (FOB)', 0, ['SUP:5.1'],
    ms=True)
row('SUP', '5.3', 'Hồ sơ xuất khẩu lô 2', 8, ['SUP:4.7'])
row('SUP', '5.4', 'Giao hàng tại cảng xuất lô 2 (FOB)', 0, ['SUP:5.3'],
    ms=True)

grp('SUP', '6', 'Hỗ trợ lắp đặt & đào tạo')
row('SUP', '6.1', 'Chuyên gia hãng vào công trường', 5, ['ERE:1.5'])
row('SUP', '6.2', 'Giám sát lắp dựng lô 1', 45, ['SUP:6.1'])
row('SUP', '6.3', 'Giám sát lắp dựng lô 2', 40, ['SUP:6.2'])
row('SUP', '6.4', 'Đào tạo nhân sự vận hành & bảo dưỡng', 15, ['SUP:6.2'])
row('SUP', '6.5', 'Cung cấp dụng cụ chuyên dùng & phụ tùng chạy thử', 15,
    ['SUP:6.1'])

grp('SUP', '7', 'Chạy thử & nghiệm thu tổ máy')
for i, w in enumerate(WTG):
    preds = ['ERE:2.%d.4' % (i + 1), 'CAB:3.%d' % (i + 1), 'SUB:5.3']
    if i:
        preds.append('SUP:7.%d' % i)
    row('SUP', '7.%d' % (i + 1), 'Chạy thử & nghiệm thu tổ máy %s' % w, 3,
        preds)
row('SUP', '7.13', 'Thử nghiệm phát điện 240 giờ toàn nhà máy', 10,
    ['SUP:7.12'])

grp('SUP', '8', 'Bàn giao & bảo hành')
row('SUP', '8.1', 'Hồ sơ hoàn công thiết bị', 10, ['SUP:7.13'])
row('SUP', '8.2', 'Nghiệm thu hoàn thành thiết bị (PAC)', 0,
    ['SUP:8.1'], ms=True)
row('SUP', '8.3', 'Bàn giao phụ tùng dự phòng & dụng cụ', 10, ['SUP:8.1'])
row('SUP', '8.4', 'Khởi động bảo hành 24 tháng', 0,
    ['SUP:8.2', 'SUP:8.3'], ms=True)

# =====================================================================
# LOG — HĐ vận chuyển siêu trường siêu trọng
# =====================================================================
grp('LOG', '1', 'Chuẩn bị & giấy phép')
row('LOG', '1.1', 'Khảo sát tuyến vận chuyển', 15)
row('LOG', '1.2', 'Lập phương án vận chuyển siêu trường', 12, ['LOG:1.1'])
row('LOG', '1.3', 'Xin giấy phép lưu hành xe quá tải trọng', 20,
    ['LOG:1.2'])
row('LOG', '1.4', 'Gia cố cầu & mở rộng bán kính cong trên tuyến', 25,
    ['LOG:1.3'])
row('LOG', '1.5', 'Huy động xe mô-đun & cẩu bốc dỡ', 18, ['LOG:1.2'])
row('LOG', '1.6', 'Tuyến vận chuyển sẵn sàng', 0, ['LOG:1.4', 'LOG:1.5'],
    ms=True)
row('LOG', '1.7', 'Khảo sát & gia cố bãi tập kết tại cảng nhập', 10,
    ['LOG:1.1'])

grp('LOG', '2', 'Vận chuyển biển lô 1')
row('LOG', '2.1', 'Đặt chỗ tàu chuyên dụng lô 1', 10, ['SUP:5.2'])
row('LOG', '2.2', 'Bốc xếp tại cảng xuất lô 1', 6, ['LOG:2.1'])
row('LOG', '2.3', 'Vận chuyển biển lô 1', 32, ['LOG:2.2'])
row('LOG', '2.4', 'Thông quan nhập khẩu lô 1', 8, ['LOG:2.3'])
row('LOG', '2.5', 'Dỡ hàng & tập kết tại cảng nhập lô 1', 6, ['LOG:2.4'])
row('LOG', '2.6', 'Lô 1 tại cảng nhập', 0, ['LOG:2.5'], ms=True)

grp('LOG', '3', 'Vận chuyển nội địa lô 1')
for i, w in enumerate(LOT1):
    preds = ['LOG:2.6', 'LOG:1.6']
    if i:
        preds.append('LOG:3.%d' % i)
    row('LOG', '3.%d' % (i + 1), 'Vận chuyển %s về công trường' % w, 4,
        preds)
row('LOG', '3.7', 'Lô 1 về công trường đủ 6 tua-bin', 0, ['LOG:3.6'],
    ms=True)

grp('LOG', '4', 'Vận chuyển biển lô 2')
row('LOG', '4.1', 'Đặt chỗ tàu chuyên dụng lô 2', 10, ['SUP:5.4'])
row('LOG', '4.2', 'Bốc xếp tại cảng xuất lô 2', 6, ['LOG:4.1'])
row('LOG', '4.3', 'Vận chuyển biển lô 2', 32, ['LOG:4.2'])
row('LOG', '4.4', 'Thông quan nhập khẩu lô 2', 8, ['LOG:4.3'])
row('LOG', '4.5', 'Dỡ hàng & tập kết tại cảng nhập lô 2', 6, ['LOG:4.4'])
row('LOG', '4.6', 'Lô 2 tại cảng nhập', 0, ['LOG:4.5'], ms=True)

grp('LOG', '5', 'Vận chuyển nội địa lô 2')
for i, w in enumerate(LOT2):
    preds = ['LOG:4.6', 'LOG:3.7']
    if i:
        preds.append('LOG:5.%d' % i)
    row('LOG', '5.%d' % (i + 1), 'Vận chuyển %s về công trường' % w, 4,
        preds)
row('LOG', '5.7', 'Lô 2 về công trường đủ 6 tua-bin', 0, ['LOG:5.6'],
    ms=True)

grp('LOG', '6', 'Bốc dỡ & tập kết tại bãi công trường')
for i, w in enumerate(WTG):
    src = 'LOG:3.%d' % (i + 1) if i < 6 else 'LOG:5.%d' % (i - 5)
    row('LOG', '6.%d' % (i + 1),
        'Bốc dỡ & kê đỡ cấu kiện %s tại bãi' % w, 2, [src, 'LOG:1.7'])

grp('LOG', '7', 'Kiểm tra & bàn giao cấu kiện tại công trường')
for i, w in enumerate(WTG):
    row('LOG', '7.%d' % (i + 1),
        'Kiểm tra cấu kiện & biên bản bàn giao %s' % w, 2,
        ['LOG:6.%d' % (i + 1)])

grp('LOG', '8', 'An toàn & hoàn tất')
row('LOG', '8.1', 'Bảo hiểm hàng hoá vận chuyển', 5, ['LOG:1.2'])
row('LOG', '8.2', 'Phương án an toàn giao thông & hộ tống', 8, ['LOG:1.3'])
row('LOG', '8.3', 'Hoàn trả gia cố cầu đường sau vận chuyển', 12,
    ['LOG:5.7'])
row('LOG', '8.4', 'Quyết toán phụ phí lưu bãi & lưu tàu', 8, ['LOG:8.3'])
row('LOG', '8.5', 'Hồ sơ vận chuyển & quyết toán hợp đồng', 10,
    ['LOG:8.4'])
row('LOG', '8.6', 'Nghiệm thu dịch vụ vận chuyển', 0,
    ['LOG:8.5', 'LOG:7.12'], ms=True)

# =====================================================================
# ERE — HĐ lắp dựng tua-bin
# =====================================================================
grp('ERE', '1', 'Huy động & thiết bị nâng')
row('ERE', '1.1', 'Khảo sát & lập biện pháp lắp dựng', 12)
row('ERE', '1.2', 'Huy động cẩu bánh xích 750 tấn', 20, ['ERE:1.1'])
row('ERE', '1.3', 'Lắp dựng cẩu chính tại bãi', 8, ['ERE:1.2', 'BOP:2.5'])
row('ERE', '1.4', 'Kiểm định cẩu & duyệt phương án an toàn', 5, ['ERE:1.3'])
row('ERE', '1.5', 'Sẵn sàng lắp dựng', 0, ['ERE:1.4'], ms=True)

grp('ERE', '2', 'Lắp dựng tua-bin')
for i, w in enumerate(WTG):
    n = i + 1
    grp('ERE', '2.%d' % n, 'Lắp dựng %s' % w)
    base = ['BOP:3.%d.4' % n, 'LOG:7.%d' % n, 'ERE:1.5']
    if i:
        base.append('ERE:2.%d.4' % i)
    row('ERE', '2.%d.1' % n, 'Lắp 3 đoạn tháp %s' % w, 4, base)
    row('ERE', '2.%d.2' % n, 'Lắp nacelle & máy phát %s' % w, 2,
        ['ERE:2.%d.1' % n])
    row('ERE', '2.%d.3' % n, 'Lắp rotor & 3 cánh %s' % w, 2,
        ['ERE:2.%d.2' % n])
    row('ERE', '2.%d.4' % n, '%s lắp dựng xong' % w, 0,
        ['ERE:2.%d.3' % n], ms=True)

grp('ERE', '3', 'Hoàn tất & rút thiết bị')
row('ERE', '3.1', 'Siết bu-lông & kiểm tra lực siết toàn bộ', 10,
    ['ERE:2.12.4'])
row('ERE', '3.2', 'Tháo & rút cẩu khỏi công trường', 10, ['ERE:3.1'])
row('ERE', '3.3', 'Nghiệm thu công tác lắp dựng', 0, ['ERE:3.2'], ms=True)

# =====================================================================
# BOP — HĐ xây lắp hạ tầng & móng
# =====================================================================
grp('BOP', '1', 'Chuẩn bị mặt bằng')
row('BOP', '1.1', 'Rà phá bom mìn vật nổ', 20)
row('BOP', '1.2', 'San dọn & đào đắp mặt bằng', 18, ['BOP:1.1'])
row('BOP', '1.3', 'Lán trại, kho bãi & văn phòng công trường', 15,
    ['BOP:1.2'])
row('BOP', '1.4', 'Cấp điện & nước thi công', 12, ['BOP:1.2'])

grp('BOP', '2', 'Đường công vụ & bãi lắp dựng')
row('BOP', '2.1', 'Đường công vụ trục chính', 30, ['BOP:1.2'])
row('BOP', '2.2', 'Đường nhánh cụm tua-bin 1–6', 20, ['BOP:2.1'])
row('BOP', '2.3', 'Đường nhánh cụm tua-bin 7–12', 20, ['BOP:2.1'])
row('BOP', '2.4', 'Bãi tập kết & bãi lắp dựng cẩu', 25, ['BOP:2.1'])
row('BOP', '2.5', 'Đường công vụ & bãi lắp dựng xong', 0,
    ['BOP:2.2', 'BOP:2.3', 'BOP:2.4'], ms=True)

grp('BOP', '3', 'Móng tua-bin')
for i, w in enumerate(WTG):
    n = i + 1
    grp('BOP', '3.%d' % n, 'Móng %s' % w)
    base = ['BOP:2.2'] if i < 6 else ['BOP:2.3']
    if i:
        base.append('BOP:3.%d.1' % i)
    row('BOP', '3.%d.1' % n, 'Đào & gia cố hố móng %s' % w, 6, base)
    row('BOP', '3.%d.2' % n, 'Cốt thép, cốp pha & lồng bu-lông neo %s' % w,
        8, ['BOP:3.%d.1' % n])
    row('BOP', '3.%d.3' % n, 'Đổ bê tông & bảo dưỡng móng %s' % w, 12,
        ['BOP:3.%d.2' % n])
    row('BOP', '3.%d.4' % n, 'Móng %s xong — sẵn sàng nhận tua-bin' % w, 0,
        ['BOP:3.%d.3' % n], ms=True)

grp('BOP', '4', 'Nhà điều hành & công trình phụ trợ')
row('BOP', '4.1', 'Móng & kết cấu nhà điều hành', 40, ['BOP:1.3'])
row('BOP', '4.2', 'Hoàn thiện kiến trúc nhà điều hành', 35, ['BOP:4.1'])
row('BOP', '4.3', 'Cấp thoát nước & hệ thống PCCC', 25, ['BOP:4.1'])
row('BOP', '4.4', 'Hàng rào, cổng & cảnh quan', 20, ['BOP:4.2'])
row('BOP', '4.5', 'Nghiệm thu nhà điều hành', 0, ['BOP:4.3', 'BOP:4.4'],
    ms=True)

grp('BOP', '5', 'Nghiệm thu & bàn giao phần BOP')
row('BOP', '5.1', 'Hoàn trả mặt bằng & vệ sinh công nghiệp', 15,
    ['ERE:3.2'])
row('BOP', '5.2', 'Hồ sơ hoàn công hạ tầng & móng', 12, ['BOP:5.1'])
row('BOP', '5.3', 'Nghiệm thu bàn giao phần BOP', 0,
    ['BOP:5.2', 'BOP:4.5'], ms=True)

# =====================================================================
# CAB — HĐ cáp ngầm 35 kV
# =====================================================================
grp('CAB', '1', 'Thiết kế & vật tư')
row('CAB', '1.1', 'Thiết kế tuyến cáp ngầm nội bộ', 20)
row('CAB', '1.2', 'Tính toán tiết diện & tổn thất điện năng', 10,
    ['CAB:1.1'])
row('CAB', '1.3', 'Chủ đầu tư duyệt thiết kế tuyến cáp', 12, ['CAB:1.2'])
row('CAB', '1.4', 'Đặt hàng cáp ngầm 35 kV', 45, ['CAB:1.3'])
row('CAB', '1.5', 'Đặt hàng đầu cốt, hộp nối & phụ kiện', 30, ['CAB:1.3'])
row('CAB', '1.6', 'Thí nghiệm mẫu cáp tại xưởng', 8, ['CAB:1.4'])
row('CAB', '1.7', 'Đặt hàng tủ đấu nối chân cột tua-bin', 25, ['CAB:1.3'])

grp('CAB', '2', 'Thi công tuyến cáp theo cụm')
for i, (cl, ws) in enumerate(CLUSTER):
    n = i + 1
    grp('CAB', '2.%d' % n, 'Cụm %s (%s)' % (cl, ', '.join(ws)))
    base = ['BOP:2.5', 'CAB:1.6']
    if i:
        base.append('CAB:2.%d.5' % i)
    row('CAB', '2.%d.1' % n, 'Đào rãnh cáp cụm %s' % cl, 8, base)
    row('CAB', '2.%d.2' % n, 'Rải cát, đặt cáp & ống bảo vệ cụm %s' % cl, 7,
        ['CAB:2.%d.1' % n])
    row('CAB', '2.%d.3' % n, 'Lấp rãnh & hoàn trả mặt bằng cụm %s' % cl, 5,
        ['CAB:2.%d.2' % n])
    row('CAB', '2.%d.4' % n, 'Thí nghiệm cách điện sau lấp cụm %s' % cl, 3,
        ['CAB:2.%d.3' % n])
    row('CAB', '2.%d.5' % n, 'Tuyến cáp cụm %s xong' % cl, 0,
        ['CAB:2.%d.4' % n], ms=True)

grp('CAB', '3', 'Đầu nối tại chân tua-bin')
for i, w in enumerate(WTG):
    n = i + 1
    cl = n // 2 if n % 2 == 0 else n // 2 + 1
    preds = ['CAB:2.%d.5' % cl, 'ERE:2.%d.4' % n, 'CAB:1.7']
    row('CAB', '3.%d' % n, 'Đầu nối & thí nghiệm cáp tại %s' % w, 3, preds)

grp('CAB', '4', 'Hào vượt & đấu nối trạm')
row('CAB', '4.1', 'Hào cáp vượt đường trục (4 vị trí)', 12, ['CAB:2.1.5'])
row('CAB', '4.2', 'Tuyến cáp về trạm nâng áp', 15, ['CAB:2.6.5'])
row('CAB', '4.3', 'Đấu nối cáp 35 kV vào tủ trung thế trạm', 8,
    ['CAB:4.2', 'SUB:4.3'])
row('CAB', '4.4', 'Lập sơ đồ hoàn công & đánh dấu tuyến cáp', 10,
    ['CAB:4.1', 'CAB:4.2'])

grp('CAB', '5', 'Thí nghiệm & nghiệm thu')
row('CAB', '5.1', 'Thí nghiệm cách điện toàn tuyến (VLF)', 12,
    ['CAB:4.3', 'CAB:3.12'])
row('CAB', '5.2', 'Hồ sơ hoàn công tuyến cáp ngầm', 10,
    ['CAB:5.1', 'CAB:4.4'])
row('CAB', '5.3', 'Nghiệm thu tuyến cáp ngầm 35 kV', 0, ['CAB:5.2'],
    ms=True)

# =====================================================================
# SUB — HĐ trạm nâng áp 110 kV & đấu nối
# =====================================================================
grp('SUB', '1', 'Thiết kế & thủ tục đấu nối')
row('SUB', '1.1', 'Thiết kế kỹ thuật trạm nâng áp 110 kV', 30)
row('SUB', '1.2', 'Thẩm tra & phê duyệt thiết kế', 15, ['SUB:1.1'])
row('SUB', '1.3', 'Thoả thuận đấu nối với đơn vị điện lực', 25, ['SUB:1.2'])
row('SUB', '1.4', 'Duyệt phương án bảo vệ relay & SCADA', 20, ['SUB:1.3'])
row('SUB', '1.5', 'Giấy phép xây dựng trạm', 20, ['SUB:1.2'])
row('SUB', '1.6', 'Hồ sơ xin phép đóng điện & phương án thí nghiệm', 15,
    ['SUB:1.3'])

grp('SUB', '2', 'Mua sắm thiết bị chính')
row('SUB', '2.1', 'Đặt hàng máy biến áp 110/35 kV', 90, ['SUB:1.2'])
row('SUB', '2.2', 'Đặt hàng tủ GIS 110 kV', 75, ['SUB:1.2'])
row('SUB', '2.3', 'Đặt hàng tủ trung thế 35 kV', 60, ['SUB:1.2'])
row('SUB', '2.4', 'Đặt hàng hệ SCADA, bảo vệ & đo đếm', 60, ['SUB:1.4'])
row('SUB', '2.5', 'Thí nghiệm xuất xưởng máy biến áp (FAT)', 10,
    ['SUB:2.1'])
row('SUB', '2.6', 'Thí nghiệm xuất xưởng tủ GIS', 8, ['SUB:2.2'])
row('SUB', '2.7', 'Thí nghiệm xuất xưởng tủ 35 kV & SCADA', 8,
    ['SUB:2.3', 'SUB:2.4'])
row('SUB', '2.8', 'Vận chuyển thiết bị trạm về công trường', 20,
    ['SUB:2.5', 'SUB:2.6', 'SUB:2.7'])
row('SUB', '2.9', 'Đặt hàng MBA tự dùng & tủ phân phối hạ thế', 45,
    ['SUB:1.2'])
row('SUB', '2.10', 'Kiểm tra vật tư phụ & cáp điều khiển', 10,
    ['SUB:2.3', 'SUB:2.9'])

grp('SUB', '3', 'Xây dựng phần trạm')
row('SUB', '3.1', 'Móng & nhà điều khiển trạm', 35, ['SUB:1.5', 'BOP:2.1'])
row('SUB', '3.2', 'Móng máy biến áp & bể dầu sự cố', 25, ['SUB:3.1'])
row('SUB', '3.3', 'Hệ thống tiếp địa & chống sét trạm', 20, ['SUB:3.1'])
row('SUB', '3.4', 'Kết cấu thép & thanh góp ngoài trời', 30, ['SUB:3.2'])
row('SUB', '3.5', 'Rãnh cáp & ống luồn nội bộ trạm', 18, ['SUB:3.3'])
row('SUB', '3.6', 'Hệ thống PCCC trạm', 18, ['SUB:3.4'])
row('SUB', '3.7', 'Chiếu sáng, camera & an ninh trạm', 15, ['SUB:3.4'])
row('SUB', '3.8', 'Sân trạm, hàng rào & đường nội bộ', 20, ['SUB:3.6'])
row('SUB', '3.9', 'Nối đất trung tính & hệ chống nhiễu', 12, ['SUB:3.3'])
row('SUB', '3.10', 'Rãnh cáp ngoài trời & giá đỡ cáp', 15, ['SUB:3.5'])

grp('SUB', '4', 'Lắp đặt & thí nghiệm thiết bị')
row('SUB', '4.1', 'Lắp đặt máy biến áp 110/35 kV', 15,
    ['SUB:2.8', 'SUB:3.4'])
row('SUB', '4.2', 'Lắp tủ GIS 110 kV', 18, ['SUB:2.8', 'SUB:3.1'])
row('SUB', '4.3', 'Lắp tủ trung thế 35 kV & cáp lực nội bộ', 15,
    ['SUB:2.8', 'SUB:3.5'])
row('SUB', '4.4', 'Lắp hệ SCADA, bảo vệ & hệ đo đếm', 20,
    ['SUB:4.2', 'SUB:4.3'])
row('SUB', '4.5', 'Thí nghiệm & hiệu chỉnh máy biến áp', 12, ['SUB:4.1'])
row('SUB', '4.6', 'Hiệu chỉnh lộ 110 kV #1 & #2', 10, ['SUB:4.2'])
row('SUB', '4.7', 'Hiệu chỉnh lộ 35 kV #1 & #2', 10, ['SUB:4.3'])
row('SUB', '4.8', 'Thí nghiệm bảo vệ relay & phối hợp bảo vệ', 15,
    ['SUB:4.4', 'SUB:4.5'])
row('SUB', '4.9', 'Thí nghiệm hệ thống đo đếm điện năng', 8, ['SUB:4.8'])
row('SUB', '4.10', 'Lắp hệ tự dùng AC/DC, ắc-quy & tủ nạp', 12,
    ['SUB:2.10', 'SUB:3.1'])
row('SUB', '4.11', 'Thí nghiệm hệ tự dùng & ắc-quy', 8, ['SUB:4.10'])
row('SUB', '4.12', 'Thí nghiệm liên động & logic khoá liên động', 10,
    ['SUB:4.8', 'SUB:4.11'])

grp('SUB', '5', 'Đóng điện')
row('SUB', '5.1', 'Kiểm tra nghiệm thu của đơn vị điện lực', 10,
    ['SUB:4.9', 'SUB:4.12', 'OHL:5.2', 'SUB:3.8', 'SUB:1.6', 'SUB:3.9',
     'SUB:3.10'])
row('SUB', '5.2', 'Đóng điện không tải & thử không tải MBA', 5, ['SUB:5.1'])
row('SUB', '5.3', 'Đóng điện (first energisation)', 0, ['SUB:5.2'], ms=True)
row('SUB', '5.4', 'Thử nghiệm ổn định 72 giờ', 3, ['SUB:5.3'])
row('SUB', '5.5', 'Nghiệm thu hệ đo đếm với đơn vị mua điện', 8,
    ['SUB:5.4'])

grp('SUB', '6', 'Tài liệu & đào tạo vận hành')
row('SUB', '6.1', 'Tài liệu vận hành & bảo dưỡng trạm', 12, ['SUB:4.9'])
row('SUB', '6.2', 'Đào tạo nhân sự vận hành trạm', 10, ['SUB:6.1'])
row('SUB', '6.3', 'Quy trình phối hợp vận hành với điều độ', 15,
    ['SUB:6.1'])
row('SUB', '6.4', 'Bàn giao hồ sơ hoàn công trạm', 10, ['SUB:6.1'])
row('SUB', '6.5', 'Nghiệm thu tài liệu & đào tạo', 0,
    ['SUB:6.2', 'SUB:6.3', 'SUB:6.4'], ms=True)

grp('SUB', '7', 'Vận hành thương mại')
row('SUB', '7.1', 'Hồ sơ nghiệm thu & công nhận COD', 10,
    ['SUB:5.4', 'SUB:5.5', 'SUB:6.5', 'SUP:7.13'])
row('SUB', '7.2', 'Vận hành thương mại (COD)', 0,
    ['SUB:7.1', 'SUP:8.2', 'CAB:5.3', 'BOP:5.3', 'ERE:3.3', 'LOG:8.6'],
    ms=True)

# =====================================================================
# OHL — HĐ đường dây 110 kV đấu nối
# =====================================================================
grp('OHL', '1', 'Thiết kế & giải phóng mặt bằng')
row('OHL', '1.1', 'Thiết kế tuyến đường dây 110 kV', 25)
row('OHL', '1.2', 'Thoả thuận tuyến với địa phương', 30, ['OHL:1.1'])
row('OHL', '1.3', 'Đền bù & giải phóng hành lang tuyến', 45, ['OHL:1.2'])
row('OHL', '1.4', 'Duyệt thiết kế kỹ thuật thi công', 15, ['OHL:1.2'])

grp('OHL', '2', 'Vật tư đường dây')
row('OHL', '2.1', 'Đặt hàng cột thép (14 vị trí)', 60, ['OHL:1.4'])
row('OHL', '2.2', 'Đặt hàng dây dẫn ACSR & cáp quang OPGW', 50,
    ['OHL:1.4'])
row('OHL', '2.3', 'Đặt hàng cách điện & phụ kiện', 40, ['OHL:1.4'])
row('OHL', '2.4', 'Kiểm tra vật tư đầu vào', 10,
    ['OHL:2.1', 'OHL:2.2', 'OHL:2.3'])

grp('OHL', '3', 'Móng & dựng cột')
for i in range(14):
    n = i + 1
    base = ['OHL:1.3', 'OHL:2.4']
    if i:
        base.append('OHL:3.%d.2' % i)
    row('OHL', '3.%d.1' % n, 'Đào & đổ móng cột VT%02d' % n, 6, base)
    row('OHL', '3.%d.2' % n, 'Dựng cột & lắp cách điện VT%02d' % n, 5,
        ['OHL:3.%d.1' % n])
    row('OHL', '3.%d.3' % n, 'Tiếp địa & sơn chống ăn mòn VT%02d' % n, 2,
        ['OHL:3.%d.2' % n])
    grp('OHL', '3.%d' % n, 'Vị trí cột VT%02d' % n)

grp('OHL', '4', 'Kéo dây & hoàn thiện')
row('OHL', '4.1', 'Kéo dây dẫn khoảng cột VT01–VT05', 15, ['OHL:3.5.2'])
row('OHL', '4.2', 'Kéo dây dẫn khoảng cột VT06–VT10', 15,
    ['OHL:3.10.2', 'OHL:4.1'])
row('OHL', '4.3', 'Kéo dây dẫn khoảng cột VT11–VT14', 12,
    ['OHL:3.14.2', 'OHL:4.2'])
row('OHL', '4.4', 'Lắp cáp quang OPGW toàn tuyến', 12, ['OHL:4.3'])
row('OHL', '4.5', 'Tiếp địa cột & biển báo an toàn', 10, ['OHL:4.3'])
row('OHL', '4.6', 'Phát quang & hoàn trả hành lang tuyến', 8, ['OHL:4.5'])

grp('OHL', '5', 'Thí nghiệm & nghiệm thu')
row('OHL', '5.1', 'Thí nghiệm cách điện & đo thông số đường dây', 10,
    ['OHL:4.4', 'OHL:4.6'])
row('OHL', '5.2', 'Nghiệm thu đường dây 110 kV', 0, ['OHL:5.1'], ms=True)

# ---------------------------------------------------------------------
# Mốc bắt đầu của các việc không có việc đứng trước
# ---------------------------------------------------------------------
ANCHOR = {
    'SUP:1.1': dt.date(2026, 2, 16),
    'LOG:1.1': dt.date(2026, 8, 3),
    'ERE:1.1': dt.date(2026, 11, 2),
    'BOP:1.1': dt.date(2026, 4, 1),
    'CAB:1.1': dt.date(2026, 5, 4),
    'SUB:1.1': dt.date(2026, 4, 1),
    'OHL:1.1': dt.date(2026, 4, 15),
}

CONTRACTS = ['SUP', 'LOG', 'ERE', 'BOP', 'CAB', 'SUB', 'OHL']


def _index():
    leaves, groups = {}, {}
    for ckey, wbs, name, dur, preds, ms, extra in ROWS:
        key = '%s:%s' % (ckey, wbs)
        if dur is None:
            groups[key] = (ckey, wbs, name)
        else:
            leaves[key] = (ckey, wbs, name, dur, preds, ms, extra)
    return leaves, groups


def schedule(with_delay):
    """Forward pass: trả {key: (start, end)} cho mọi việc lá."""
    leaves, _ = _index()
    out, visiting = {}, set()

    def solve(key):
        if key in out:
            return out[key]
        if key in visiting:
            raise RuntimeError('Phụ thuộc vòng tại %s' % key)
        visiting.add(key)
        ckey, wbs, name, dur, preds, ms, extra = leaves[key]
        starts = []
        for p in preds:
            if p not in leaves:
                raise KeyError('%s trỏ tới việc không có: %s' % (key, p))
            starts.append(solve(p)[1] + dt.timedelta(days=1))
        if key in ANCHOR:
            starts.append(ANCHOR[key])
        if not starts:
            raise KeyError('%s không có việc trước và không có mốc bắt đầu'
                           % key)
        start = max(starts)
        d = dur + (extra if with_delay else 0)
        end = start + dt.timedelta(days=max(d - 1, 0))
        visiting.discard(key)
        out[key] = (start, end)
        return out[key]

    for k in leaves:
        solve(k)
    return out


def roll_groups(dates):
    """Ngày của dòng tổng = bao trùm các dòng con."""
    leaves, groups = _index()
    res = {}
    for gkey in groups:
        pre = gkey + '.'
        kids = [v for k, v in dates.items() if k.startswith(pre)]
        if kids:
            res[gkey] = (min(k[0] for k in kids), max(k[1] for k in kids))
    return res


def build():
    """Trả danh sách dòng kèm ngày hiện hành + ngày baseline."""
    cur, base = schedule(True), schedule(False)
    cur.update(roll_groups(cur))
    base.update(roll_groups(base))
    rows = []
    for ckey, wbs, name, dur, preds, ms, extra in ROWS:
        key = '%s:%s' % (ckey, wbs)
        if key not in cur:
            continue
        rows.append({
            'key': key, 'contract': ckey, 'wbs': wbs, 'name': name,
            'is_group': dur is None, 'milestone': ms,
            'preds': list(preds),
            'start': cur[key][0], 'end': cur[key][1],
            'bstart': base[key][0], 'bend': base[key][1],
        })
    return rows


if __name__ == '__main__':
    rows = build()
    print('Tổng dòng:', len(rows))
    for c in CONTRACTS:
        rs = [r for r in rows if r['contract'] == c]
        leaf = [r for r in rs if not r['is_group']]
        print('%-4s %3d dòng (%3d việc, %2d dòng tổng)  %s → %s'
              % (c, len(rs), len(leaf), len(rs) - len(leaf),
                 min(r['start'] for r in rs), max(r['end'] for r in rs)))
    by = {r['key']: r for r in rows}
    for k in ['SUP:3.2', 'SUP:3.6', 'LOG:3.7', 'BOP:3.1.4', 'ERE:2.1.4',
              'ERE:2.12.4', 'SUB:5.3', 'SUP:7.13', 'SUB:7.2']:
        r = by[k]
        print('%-12s %-46s HH %s→%s | BL %s→%s | lệch %+d'
              % (k, r['name'][:46], r['start'], r['end'], r['bstart'],
                 r['bend'], (r['end'] - r['bend']).days))
    print('Về đích hiện hành:', max(r['end'] for r in rows),
          '| baseline:', max(r['bend'] for r in rows))
