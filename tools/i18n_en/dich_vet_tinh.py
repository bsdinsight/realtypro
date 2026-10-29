# -*- coding: utf-8 -*-
"""Dịch các VẾT TÍNH TOÁN đã lưu sang tiếng Anh.

Đây là chuỗi do chính phần mềm sinh lúc tính rồi lưu vào cột — "sản
lượng lấy từ đâu", "vì sao chưa đo được". Chúng là thứ làm nên giá trị
của hệ: mỗi con số đều nói được nó từ đâu ra. Nhưng vì đã LƯU, đổi
ngôn ngữ giao diện không đổi được chúng.

Hai cách, và vì sao chọn cách này:

* **Tính lại** toàn bộ dưới ngữ cảnh `en_GB`. Đúng về nguyên tắc, nhưng
  phải dựng lại ~4.000 bản ghi ngày trên hệ thống khách ĐANG DÙNG, và
  mọi con số đều được tính lại — rủi ro không tương xứng với việc chỉ
  muốn đổi chữ.
* **Dịch thẳng chuỗi đã lưu.** 58.007 ô nhưng chỉ 253 giá trị khác
  nhau, và chúng sinh ra từ vài chục khuôn `_()`. Dịch khuôn là xong,
  số liệu không ai đụng tới.

Chọn cách thứ hai. Khuôn viết bằng regex để GIỮ NGUYÊN mọi con số, mã
bậc đo và mốc thời gian nhúng bên trong — đó mới là phần mang thông tin.

Các trường này `translate=False` nên phải ghi đè: bản tiếng Việt mất.
Chấp nhận được vì đây là vết máy sinh, không phải chữ người viết, và
lần tính lại sau sẽ sinh lại theo ngôn ngữ lúc ấy.
"""
import re

print('@@@BATDAU')

VIET = re.compile('[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợ'
                  'ùúủũụưừứửữựỳýỷỹỵđÀÁẢÃẠĂÂÊÔƠƯĐ]')

VET = [
    ('eam.unit.day', ['nguon_cs', 'nguon_sl', 'ghi_chu', 'ly_do_dc',
                      'ly_do_kd', 'ly_do_sl', 'ly_do_hs']),
    ('eam.energy.period', ['ly_do_khong_so']),
    ('eam.loss.day.line', ['nguon', 'ly_do']),
    ('eam.loss.day', ['ly_do_tn', 'ly_do_kh']),
    ('eam.availability.day', ['nguon_sl', 'ly_do_chua_do']),
    ('eam.alarm', ['message']),
]

# Tên nhóm giờ dừng và tên bậc đo nhúng trong câu — lấy đúng bản đã
# dùng ở danh mục loại tổn thất, để hai màn không gọi một thứ hai tên.
NHUNG = {
    'Bảo trì theo kế hoạch': 'Planned maintenance',
    'Bất khả kháng & môi trường': 'Force majeure & environment',
    'Cắt giảm theo lệnh điều độ': 'Dispatch curtailment',
    'Dừng do lưới ngoài': 'External grid outage',
    'Dừng do nhà thầu O&M': 'O&M contractor downtime',
    'Mất dữ liệu giám sát': 'Monitoring data gap',
    'Sự cố ngoài phạm vi': 'Out-of-scope failure',
    'Sự cố thiết bị': 'Equipment failure',
    'Bậc sản lượng': 'Energy step',
    'Tiêu thụ ban đêm': 'Night-time consumption',
    'Điện tự dùng': 'Auxiliary consumption',
    'Công-tơ bán điện': 'Sales meter',
    'Điểm đấu nối EVN': 'EVN connection point',
    'Cam kết hợp đồng — tua-bin': 'Contract commitment — turbine',
    'Cam kết trong hợp đồng': 'contract commitment',
    'Nhiệt độ dầu hộp số': 'Gearbox oil temperature',
    'Công suất tác dụng': 'Active power',
    'Tốc độ rotor': 'Rotor speed',
}

MAU = [
    (r'^nạp số liệu lịch sử$', 'historical data load'),
    (r'^nạp lịch sử (\S+)$', r'historical load \1'),
    (r'^công suất đặt khai trên vị trí$',
     'rated power declared on the location'),
    (r'^đường cong công suất "(.+)"$', r'power curve "\1"'),
    (r'^cộng điện năng (\d+) tổ máy \(số SCADA\)$',
     r'sum of energy over \1 units (SCADA figures)'),
    (r'^tổ máy chưa khai điểm đo phía một chiều$',
     'the unit has no DC-side tag declared'),
    (r'^điểm đo phía một chiều không có số trong ngày$',
     'the DC-side tag has no readings on this day'),
    (r'^tổ máy không có điểm đo điện năng nào có số trong ngày này$',
     'the unit has no energy tag with readings on this day'),
    (r'^chưa có sản lượng thì chưa có tử số$',
     'without generation there is no numerator'),
    (r'^loại này do người nhập tay$', 'this category is entered manually'),
    (r'^ngày này chưa có dòng hiệu suất$',
     'no performance row exists for this day'),
    (r'^chưa khai mục tiêu cho tháng (.+?) của nhà máy này$',
     r'no target declared for \1 at this plant'),
    (r'^chưa khai mục tiêu cho tháng (.+)$', r'no target declared for \1'),
    (r'^không có khoảng dừng nhóm "(.+?)" trong ngày$',
     r'no outage in group "\1" on this day'),
    (r'^bậc "(\S+)" chưa có dòng ngày$', r'step "\1" has no daily row'),
    (r'^bậc (\S+) · (.+)$', r'step \1 · \2'),
    (r'^bậc bán điện "(.+?)", (\d+) ngày$', r'sales meter step "\1", \2 days'),
    (r'^(\d+) khoảng dừng · ([\d\.,]+) giờ-máy$',
     r'\1 outages · \2 unit-hours'),
    (r'^(\d+) tổ máy có số hai phía, không mốc nào chạm trần$',
     r'\1 units have readings on both sides, no sample at the ceiling'),
    (r'^(\d+)/(\d+) tổ máy có lúc chạm trần$',
     r'\1/\2 units hit the ceiling at some point'),
    (r'^không tổ máy nào có số phía một chiều — không biết DC có vượt '
     r'trần AC hay không$',
     'no unit has DC-side readings — we cannot tell whether DC exceeded '
     'the AC ceiling'),
    (r'^chưa tổ máy nào gắn đường cong công suất — không suy được "lẽ ra '
     r'phát bao nhiêu với gió hôm nay"$',
     'no unit has a power curve attached — we cannot derive "what it '
     'should have produced with today’s wind"'),
    (r'^không tổ máy nào có số đo gió trong ngày$',
     'no unit has wind readings on this day'),
    (r'^bức xạ × diện tích × hiệu suất mô-đun, ở điều kiện chuẩn — phần '
     r'hụt do nhiệt hiện thành cột riêng$',
     'irradiance × area × module efficiency, at standard conditions — the '
     'thermal shortfall appears as its own column'),
    (r'^\(1 − Ft\) × mốc chuẩn · Ft = ([\d\.]+), mốc tham chiếu ([\d\.]+) '
     r'°C, mô-đun ([\d\.]+) °C$',
     r'(1 − Ft) × standard reference · Ft = \1, reference point \2 °C, '
     r'module \3 °C'),
    (r'^nhà máy chưa khai chuỗi điểm đo có bậc bán điện, và cũng chưa có '
     r'điểm đo điện năng nào có số trong khoảng này — không có sản lượng '
     r'thực thì không có tử số$',
     'the plant has no measurement chain with a sales-meter step, and no '
     'energy tag has readings in this window — without actual generation '
     'there is no numerator'),
    (r'^sản lượng thực và sản lượng mất đều bằng 0 trong khoảng này — chia '
     r'cho 0 thì ra số vô nghĩa, nên để trống$',
     'both actual and lost generation are zero in this window — dividing '
     'by zero gives a meaningless figure, so it is left blank'),
    (r'^(\d+)/(\d+) tổ máy thiếu số đo gió: (.+)$',
     r'\1/\2 units are missing wind readings: \3'),
    (r'^(\d+)/(\d+) mốc đo có gió VƯỢT dải đường cong — không biết là máy '
     r'đã cắt vì bão hay đường cong chỉ khai tới đó, nên không cộng vào '
     r'mốc; mốc tài nguyên đang THẤP hơn thật đúng phần ấy$',
     r'\1/\2 samples have wind ABOVE the published curve range — we cannot '
     r'tell a storm shutdown from a curve declared only that far, so they '
     r'are not added; the resource level is UNDERSTATED by exactly that much'),
    (r'^chưa khai mục tiêu$', 'no target declared'),
    # ---- thông báo cảnh báo ----
    (r'^(.+?) — (\S+) đang ([\d\.]+) °C — nằm ngoài dải ([\d\.]+)–([\d\.]+), '
     r'liên tục (\d+) phút \((\d+) số đo, không có mốc nào ngược lại\)\.$',
     r'\1 — \2 is at \3 °C — outside the \4–\5 band, sustained for \6 '
     r'minutes (\7 readings, none to the contrary).'),
    (r'^(.+?) — (\S+) đang ([\d\.]+) °C — vượt quá ngưỡng ([\d\.]+), '
     r'liên tục (\d+) phút \((\d+) số đo, không có mốc nào ngược lại\)\.$',
     r'\1 — \2 is at \3 °C — above the \4 threshold, sustained for \5 '
     r'minutes (\6 readings, none to the contrary).'),
    (r'^(.+?) — (\S+) đứng im ở ([\d\.]+) suốt (\d+) phút — số vẫn về đều '
     r'nên KHÔNG phải mất tín hiệu, mà là giá trị không đổi\. Hai chuyện '
     r'ấy sửa ở hai nơi khác nhau\.$',
     r'\1 — \2 frozen at \3 for \4 minutes — readings keep arriving, so '
     r'this is NOT a lost signal but a value that never changes. The two '
     r'are fixed in different places.'),
    (r'^(.+?) — (\S+) ngừng gửi số đã ([\d\.]+) giờ \(mốc cuối (.+?)\)\. '
     r'Trong lúc nó im, mọi luật ngưỡng canh trên chính điểm đo này cũng '
     r'im theo — kiểm ĐƯỜNG TRUYỀN trước khi cử người ra trụ\.$',
     r'\1 — \2 has not sent data for \3 hours (last sample \4). While it '
     r'is silent, every threshold rule watching this tag is silent too — '
     r'check the COMMUNICATION PATH before sending anyone to the tower.'),
    (r'^Hai cảm biến lệch ([\d\.]+)%: (\S+) đang ([\d\.]+), (\S+) đang '
     r'([\d\.]+)\. Một trong hai đã trôi — và nhìn riêng từng cái thì cả '
     r'hai đều nằm trong dải hợp lý, nên chỉ phép so này mới thấy\.$',
     r'The two sensors differ by \1%: \2 reads \3, \4 reads \5. One of '
     r'them has drifted — and taken on its own each sits in a plausible '
     r'range, so only this comparison reveals it.'),
    (r'^Không có số đọc mới (\d+) ngày \(lần cuối (.+?)\)\. Nhiều khả năng '
     r'ĐƯỜNG TRUYỀN chết, không phải máy dừng — kiểm tra kết nối trước khi '
     r'cử người ra trụ\.$',
     r'No new reading for \1 days (last one \2). Most likely the '
     r'COMMUNICATION PATH is dead rather than the machine being stopped — '
     r'check the link before sending anyone to the tower.'),
]
MAU = [(re.compile(a), b) for a, b in MAU]
# nhúng: dài trước
NH = sorted(NHUNG.items(), key=lambda x: -len(x[0]))


def dich(s):
    for rx, thay in MAU:
        if rx.match(s):
            ra = rx.sub(thay, s)
            for a, b in NH:
                ra = ra.replace(a, b)
            return ra
    return None


dat = 0
chua = {}
for mn, cols in VET:
    if mn not in env:
        continue
    M = env[mn].with_context(active_test=False)
    cols = [c for c in cols if c in M._fields]
    for r in M.search([]):
        v = {}
        for c in cols:
            cur = r[c]
            if not cur or not isinstance(cur, str) or not VIET.search(cur):
                continue
            en = dich(cur)
            if en:
                v[c] = en
            else:
                chua.setdefault(cur, 0)
                chua[cur] += 1
        if v:
            r.write(v)
            dat += len(v)
    env.cr.commit()
    print('   %-22s xong' % mn)

print('ĐÃ DỊCH %d ô vết · chưa khớp %d chuỗi (%d ô)'
      % (dat, len(chua), sum(chua.values())))
for s, n in sorted(chua.items(), key=lambda x: -x[1])[:20]:
    print('   %5d  %s' % (n, s[:95]))
