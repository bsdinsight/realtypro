# -*- coding: utf-8 -*-
"""Dịch DỮ LIỆU MẪU của EAMOne sang tiếng Anh trên bản demo.

Khác mọi script dịch khác ở đây: đây là DỮ LIỆU do seed sinh ra, không
có xmlid, nên không có đường `.po` nào cả — phải ghi thẳng giá trị.

Ba tầng, thử theo thứ tự:

1. **Mẫu sinh tự động** — câu do chính phần mềm dựng, có ngày tháng và
   số chứng từ nhúng bên trong ("Bảo hành 60 tháng kể từ ngày nghiệm
   thu bàn giao 2023-03-18 …"). Dịch bằng regex, GIỮ NGUYÊN phần số.
   Dịch tay từng câu là 500 dòng gần giống nhau, và sai một ngày thì
   không ai soát ra.
2. **Gốc từ + mã đuôi** — "Hộp số T07" = gốc "Hộp số" + mã "T07". Tên
   thiết bị lặp 42 lần một kiểu, nên dịch gốc rồi ghép lại mã.
3. **Nguyên câu** — phần còn lại, tra bảng đúng-nguyên-văn.

Ô nào không khớp tầng nào thì GIỮ NGUYÊN và in ra cuối. Đoán bừa một
bản dịch cho câu không nhận ra là cách chắc chắn nhất để một con số
hoặc một mã chứng từ bị viết sai mà không ai thấy.

Trường có `translate=True` thì ghi vào `en_GB`, giữ nguyên bản tiếng
Việt. Trường `translate=False` thì BUỘC phải ghi đè — script in riêng
danh sách ấy ra để còn quyết định có mở `translate` cho chúng không.
"""
import re

print('@@@BATDAU')

VIET = re.compile('[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợ'
                  'ùúủũụưừứửữựỳýỷỹỵđÀÁẢÃẠĂÂÊÔƠƯĐ]')

# Model có cột là VẾT TÍNH TOÁN do Python sinh rồi lưu — tính lại là ra
# tiếng Anh (nhờ các dấu odoo-python đã vá), không dịch ở đây.
BO_MODEL = {'eam.unit.day', 'eam.loss.day.line', 'eam.loss.day',
            'eam.energy.period', 'eam.availability.day', 'eam.alarm'}
BO_COT = {'complete_name'}          # tự sinh từ cha + con

# KHOÁ KHỚP khi nạp dữ liệu, KHÔNG phải chữ hiển thị. `alias_names` là
# danh sách từ đồng nghĩa để bộ nhập nhận ra một hạng mục viết theo
# nhiều kiểu; dịch nó đi là hỏng chức năng nhập, và hỏng im lặng — tệp
# vẫn nạp, chỉ là không khớp được hạng mục nào nữa. Đã lỡ ghi đè 2 ô ở
# lượt đầu rồi phải phục hồi từ bản dump.
BO_KHOA = {('eam.asset.category', 'alias_names'),
           ('product.template', 'eam_spec_key')}

# ---- tầng 1: mẫu sinh tự động ------------------------------------
MAU = [
    (r'^Bảo hành (\d+) tháng kể từ ngày nghiệm thu bàn giao (\S+) của chính vị trí này\.$',
     r'\1-month warranty from the handover acceptance date \2 of this location.'),
    (r'^Bảo hành thiết bị (\d+) năm kể từ ngày vận hành thương mại\.$',
     r'\1-year equipment warranty from the commercial operation date.'),
    (r'^Bảo hành (\d+) tháng kể từ ngày nhận hàng$',
     r'\1-month warranty from the goods receipt date'),
    (r'^Theo bảo hành thiết bị (\d+) năm\.$', r'Per the \1-year equipment warranty.'),
    (r'^Nhập từ hệ giám sát$', 'Imported from the monitoring system'),
    (r'^Bàn giao (\S+) · \(chưa rõ hợp đồng\)$', r'Handover \1 · (contract not identified)'),
    (r'^Bàn giao (\S+) · HĐ (.+?) · lô: (.+)$', r'Handover \1 · contract \2 · lots: \3'),
    (r'^kéo từ biên bản bàn giao (\S+), vị trí (\S+) \(liệt kê đích danh máy(.*)$',
     r'taken from handover record \1, location \2 (machine listed by name\3'),
    (r'^biểu giá (\S+), kỳ (\S+) → (\S+)$', r'tariff \1, period \2 → \3'),
    (r'^chưa hỏng lần nào nên chưa có MTBF$', 'no failures yet, so no MTBF'),
    (r'^chưa ghi giờ sửa nên chưa có MTTR$', 'no repair hours recorded, so no MTTR'),
    (r'^Hạn (\S+) rơi vào (.+?) \(Nên tránh: (.+?)\)(.*)$',
     r'Due date \1 falls in \2 (best avoided: \3)\4'),
    (r'^Hạn rơi vào (.+?) \(Nên tránh: (.+?)\)(.*)$',
     r'Due date falls in \1 (best avoided: \2)\3'),
    (r'^Hạn kiểm định rơi vào (.+?) \(Nên tránh: (.+?)\)(.*)$',
     r'Statutory inspection due date falls in \1 (best avoided: \2)\3'),
    (r'^Bộ biến tần (\d+) ngừng phát$', r'Inverter \1 stopped generating'),
    (r'^Bộ biến tần trung tâm (\d+)$', r'Central inverter \1'),
    (r'^Bảo trì (\d+) tháng theo kế hoạch$', r'\1-month planned maintenance'),
    (r'^chỉ có (\d+) tổ máy đối chứng có số đo trong khoảng này, cần ít nhất (\d+)(.*)$',
     r'only \1 peer units have readings in this window, at least \2 are needed\3'),
    (r'^Hộp gom (\S+) \((\d+) chuỗi\)$', r'Combiner box \1 (\2 strings)'),
    (r'^Cảm biến POA — trạm khí tượng (\S+)$', r'POA sensor — weather station \1'),
    (r'^HĐ (.+)$', r'Contract \1'),
    (r'^Chờ nhà thầu trả lời về cầu chì chuỗi (\S+)$',
     r'Awaiting the contractor reply on the string fuses of \1'),
    (r'^Inverter (\S+) báo lỗi cách điện, đã reset — theo dõi tiếp$',
     r'Inverter \1 reported an insulation fault, reset — keep watching'),
    (r'^Báo cáo khả thi — mô phỏng PVsyst (\S+)$',
     r'Feasibility study — PVsyst \1 simulation'),
    (r'^(.*?)Lịch theo mùa: Hạn (\S+) rơi vào (.+?) \(Nên tránh: (.+?)\)\.'
     r' Đề xuất kéo lên sớm (\d+) ngày, làm ngày (\S+)\.$',
     r'\1Seasonal schedule: the \2 due date falls in \3 (best avoided: \4). '
     r'Suggested: bring forward by \5 days, to be done on \6.'),
    (r'^Lịch theo mùa: Hạn (\S+) rơi vào (.+?) \(Nên tránh: (.+?)\)\.'
     r' Đề xuất kéo lên sớm (\d+) ngày, làm ngày (\S+)\.$',
     r'Seasonal schedule: the \1 due date falls in \2 (best avoided: \3). '
     r'Suggested: bring forward by \4 days, to be done on \5.'),
]
MAU = [(re.compile(a), b) for a, b in MAU]

# ---- tầng 2: gốc từ (tên thiết bị, điểm đo, danh mục) -------------
GOC = {
    # tua-bin gió
    'Hộp số': 'Gearbox', 'Máy phát': 'Generator', 'Moay-ơ': 'Hub',
    'Tháp': 'Tower', 'Móng': 'Foundation', 'Cánh': 'Blade',
    'Phanh cơ': 'Mechanical brake', 'Hệ yaw': 'Yaw system',
    'Hệ pitch': 'Pitch system', 'Hệ thuỷ lực': 'Hydraulic system',
    'Bộ điều khiển': 'Controller', 'Bộ biến tần': 'Inverter',
    'Máy biến áp máy': 'Unit transformer',
    'Trục & ổ trục chính': 'Main shaft & main bearing',
    'Vỏ nacelle & thiết bị nâng': 'Nacelle cover & lifting equipment',
    'Cụm truyền động': 'Drive train assembly', 'Cụm điện': 'Electrical assembly',
    'Cụm rotor': 'Rotor assembly', 'Cụm kết cấu': 'Structural assembly',
    'Cụm cảm biến & đo gió': 'Sensor & wind measurement assembly',
    'Tua-bin gió': 'Wind turbine', 'Cảm biến': 'Sensors', 'Hệ điện': 'Electrical system',
    'Bảo vệ và đóng cắt': 'Protection & switchgear', 'Máy biến áp': 'Transformer',
    'Hệ điều khiển': 'Control system',
    # điện mặt trời
    'Hộp gom': 'Combiner box', 'Dàn pin': 'PV array', 'Hệ xoay': 'Tracker',
    'Khung giá đỡ': 'Mounting structure', 'Làm mát': 'Cooling',
    'Phía một chiều': 'DC side', 'Phía xoay chiều': 'AC side',
    'Điều khiển & truyền thông': 'Control & communications',
    'Điều khiển hệ xoay': 'Tracker control', 'Cơ cấu truyền động': 'Drive mechanism',
    'Bộ biến tần quang điện': 'PV inverter', 'Bộ biến tần tua-bin': 'Turbine converter',
    'Dàn pin quang điện': 'PV array', 'Chuỗi tấm pin': 'PV string',
    'Tấm pin': 'PV module', 'Hộp gom chuỗi': 'String combiner box',
    'Bộ giám sát dòng chuỗi': 'String current monitor', 'Cầu chì chuỗi': 'String fuse',
    'Hệ xoay theo mặt trời': 'Solar tracker',
    'Hệ thống phụ trợ nhà máy': 'Plant balance of system',
    'Cáp ngầm trung thế': 'MV underground cable',
    'Đường dây truyền tải': 'Transmission line',
    'Hạ tầng dân dụng': 'Civil works', 'Khác (phụ trợ)': 'Other (balance of plant)',
    'SCADA và truyền thông': 'SCADA & communications',
    # trạm biến áp
    'Trạm biến áp': 'Substation', 'Trạm nâng áp': 'Step-up substation',
    'Máy biến áp lực': 'Main power transformer',
    'Bộ điều áp dưới tải': 'On-load tap changer',
    'Đồng hồ nhiệt độ dầu và cuộn dây': 'Oil & winding temperature gauges',
    'Hệ dầu và bình giãn nở': 'Oil system & conservator',
    'Hệ làm mát máy biến áp': 'Transformer cooling system',
    'Hệ làm mát': 'Cooling system', 'Nối đất trung tính': 'Neutral earthing',
    'Rơ-le hơi và bảo vệ bản thể': 'Buchholz relay & body protection',
    'Sứ xuyên': 'Bushing', 'Ngăn lộ cao áp': 'HV bay',
    'Biến điện áp đo lường': 'Measurement voltage transformer',
    'Biến dòng đo lường': 'Measurement current transformer',
    'Chống sét van': 'Surge arrester',
    'Chống sét van trung áp': 'MV surge arrester',
    'Dao cách ly và dao tiếp địa': 'Disconnector & earthing switch',
    'Máy cắt': 'Circuit breaker', 'Ngăn lộ trung áp': 'MV bay',
    'Thanh cái và tủ hợp bộ': 'Busbar & switchgear cubicles',
    'Nguồn tự dùng và một chiều': 'Auxiliary & DC supply',
    'Bộ nạp và tủ phân phối một chiều': 'Charger & DC distribution board',
    'Hệ ắc-quy một chiều': 'DC battery system',
    'Máy biến áp tự dùng': 'Auxiliary transformer',
    'Thiết bị bù công suất phản kháng': 'Reactive power compensation',
    'Bộ biến đổi bù': 'Compensation converter', 'Tủ tụ bù': 'Capacitor bank cubicle',
    'Hệ bảo vệ và điều khiển': 'Protection & control system',
    'Rơ-le bảo vệ': 'Protection relay',
    'RTU và cổng truyền thông SCADA': 'RTU & SCADA gateway',
    'Hệ nối đất và chống sét': 'Earthing & lightning protection',
    'Hệ thống chữa cháy trạm': 'Substation fire-fighting system',
    'Đo đếm điện năng giao nhận': 'Revenue metering',
    # khí tượng & điểm đo
    'Trạm khí tượng': 'Weather station', 'Cảm biến bức xạ': 'Irradiance sensor',
    'Cảm biến gió': 'Wind sensor', 'Cảm biến nhiệt độ': 'Temperature sensor',
    'Điện năng luỹ kế': 'Cumulative energy', 'Công suất tác dụng': 'Active power',
    'Công suất AC': 'AC power', 'Công suất một chiều': 'DC power',
    'Công suất AC toàn nhà máy': 'Plant AC power',
    'Trạng thái chạy': 'Running status', 'Tốc độ gió': 'Wind speed',
    'Hướng gió': 'Wind direction', 'Tốc độ rotor': 'Rotor speed',
    'Nhiệt độ dầu hộp số': 'Gearbox oil temperature',
    'Nhiệt độ bộ biến tần': 'Inverter temperature',
    'Nhiệt độ môi trường': 'Ambient temperature',
    'Nhiệt độ mô-đun': 'Module temperature',
    'Độ ẩm tương đối': 'Relative humidity',
    'Áp suất khí quyển': 'Atmospheric pressure', 'Hệ số tải': 'Load factor',
    'Bức xạ mặt phẳng dàn pin': 'Plane-of-array irradiance',
    'Cảm biến POA': 'POA sensor',
    # kho
    'Kho trung tâm': 'Central store', 'Kho hiện trường': 'Site store',
    'Kho nhà thầu O&M': 'O&M contractor store', 'Cách ly': 'Quarantine',
    'Chờ kiểm tra': 'Awaiting inspection', 'Chờ đại tu': 'Awaiting overhaul',
    'Hỏng — chờ thanh lý': 'Scrap — awaiting disposal',
    'Khu A — phụ tùng lớn': 'Zone A — major spares',
    'Khu B — vật tư nhỏ': 'Zone B — small parts',
    'Khu C — dầu mỡ': 'Zone C — oils & greases',
    'Đã lắp lên thiết bị': 'Installed on equipment',
    'Hàng đang đi giữa kho': 'In transit between stores',
    'Tiêu dùng bảo trì': 'Maintenance consumption',
    'giờ': 'hours', 'Lít': 'Litre',
}
# Mã ở đuôi: T07, INV03-2, (2 chuỗi), số 3…
MA_DUOI = re.compile(r'^(?P<goc>.*?)(?P<ma>\s*(?:—\s*)?'
                     r'(?:[A-Z]{1,5}[0-9][0-9A-Za-z\-\./]*'
                     r'|\([0-9][^)]*\)|số\s*\d+))$')
# "Cánh số 2 T05" — mã nằm giữa
CANH = re.compile(r'^Cánh số (\d+) (T\d+)$')

# ---- tầng 3: nguyên câu ------------------------------------------
NGUYEN = {
    'Mất số đọc đồng hồ giờ máy chạy': 'Run-hour meter reading lost',
    'Tua-bin đứng im (giờ chạy không tăng)':
        'Turbine idle (run hours not increasing)',
    'Vòng quay đứng im khi đang có gió':
        'Rotor speed frozen while wind is present',
    'Điểm đo ngừng gửi số': 'Tag stopped sending data',
    'Nhiệt độ dầu hộp số cao': 'Gearbox oil temperature high',
    'Nhiệt độ hộp số ngoài dải vận hành':
        'Gearbox temperature outside the operating band',
    'Hai cảm biến tốc độ gió lệch nhau': 'Wind speed sensors disagree',
    'Rò dầu hộp số': 'Gearbox oil leak',
    'Nền tảng 4,0 MW · rô-to 150 m': '4.0 MW platform · 150 m rotor',
    'Nền tảng 6,24 MW · rô-to 171 m': '6.24 MW platform · 171 m rotor',
    'Nền tảng 4,0 MW · rô-to 150 m, Nền tảng 6,24 MW · rô-to 171 m':
        '4.0 MW platform · 150 m rotor, 6.24 MW platform · 171 m rotor',
    'Theo khuyến cáo bảo quản của hãng chế tạo.':
        "Per the manufacturer's storage recommendations.",
    'Hộp số thay thế — bảo hành riêng, ngắn hơn máy.':
        'Replacement gearbox — separate warranty, shorter than the machine.',
    'Hộp số thay thế đã tân trang — bảo hành riêng, ngắn hơn máy.':
        'Refurbished replacement gearbox — separate warranty, shorter than '
        'the machine.',
    'Chờ nhà thầu trả lời về cầu chì chuỗi':
        'Awaiting the contractor reply on the string fuses',
    'Inverter INV03 báo lỗi cách điện, đã reset — theo dõi tiếp':
        'Inverter INV03 reported an insulation fault, reset — keep watching',
    'Chưa có nơi quản lý — cần quyết định đặt ở đâu':
        'No owner yet — a location still has to be decided',
    'Thủ kho duyệt — từ 20 triệu': 'Storekeeper approval — from VND 20m',
    'Quản lý kho duyệt — từ 200 triệu': 'Store manager approval — from VND 200m',
    'Vật tư quay vòng — luôn phải quản lý kho duyệt':
        'Rotables — always require store manager approval',
    'Mức thường ngày, thủ kho tự quyết.':
        'Everyday level, the storekeeper decides.',
    'Báo cáo mô phỏng gió, phụ lục 3 HĐ vay':
        'Wind simulation report, appendix 3 of the loan agreement',
    'Báo cáo khả thi — mô phỏng PVsyst': 'Feasibility study — PVsyst simulation',
    'PVsyst — dải thiết kế ĐMT mặt đất':
        'PVsyst — design range for ground-mounted PV',
    'Trung tâm Kỹ thuật TC Đo lường CL 3':
        'Quality Assurance and Testing Centre 3',
    'IEC 61400-26-1:2019 phụ lục B (tuỳ chọn)':
        'IEC 61400-26-1:2019 annex B (optional)',
    # ---- vật tư & phụ tùng (kho) ----
    'Ắc-quy hệ pitch — bộ 3 trục': 'Pitch system battery — set of 3 axes',
    'Bảo hiểm mọi rủi ro xây dựng (CAR) — 14 tháng':
        "Contractor's all risks insurance (CAR) — 14 months",
    'Bộ bảo hộ lao động': 'Personal protective equipment set',
    'Bộ biến đổi toàn phần (FSC) — 6,24 MW': 'Full-scale converter (FSC) — 6.24 MW',
    'Bộ điều khiển hệ xoay (NCU)': 'Tracker control unit (NCU)',
    'Bộ lọc dầu hộp số': 'Gearbox oil filter',
    'Bộ lưu điện tủ điều khiển nacelle': 'Nacelle control cabinet UPS',
    'Bơm thuỷ lực hệ pitch': 'Pitch system hydraulic pump',
    'Bộ vệ sinh tấm pin — chổi + nước khử khoáng':
        'PV module cleaning kit — brush + demineralised water',
    'Cảm biến hướng gió (wind vane)': 'Wind vane',
    'Cảm biến tốc độ gió (anemometer)': 'Anemometer',
    'Cánh quạt thay thế — 82 m': 'Replacement blade — 82 m',
    'Cầu chì chuỗi DC 15 A / 1000 V (gPV) — hộp 10':
        'DC string fuse 15 A / 1000 V (gPV) — box of 10',
    'Chổi than máy phát — bộ': 'Generator carbon brushes — set',
    'Chống sét lan truyền DC Type 2 — bộ 3':
        'DC surge protection device Type 2 — set of 3',
    'Cờ-lê lực 100–1.000 Nm': 'Torque wrench 100–1,000 Nm',
    'Dầu hộp số tổng hợp — phuy 200 L': 'Synthetic gearbox oil — 200 L drum',
    'Đầu nối MC4 + cáp DC 4 mm² — bộ 50':
        'MC4 connectors + 4 mm² DC cable — set of 50',
    'Hộp số thay thế — 6,24 MW': 'Replacement gearbox — 6.24 MW',
    'Kiểm định & thí nghiệm vật liệu, nghiệm thu nhà nước':
        'Statutory inspection & material testing, state acceptance',
    'Lọc thuỷ lực': 'Hydraulic filter',
    'Lưới lọc bụi tủ biến tần — bộ': 'Inverter cabinet dust filter — set',
    'Má phanh đĩa cơ — bộ': 'Mechanical disc brake pads — set',
    'Máy biến áp tua-bin 6,6/33 kV — 7 MVA': 'Turbine transformer 6.6/33 kV — 7 MVA',
    'Máy đo điện trở cách điện 5 kV': 'Insulation resistance tester 5 kV',
    'Máy đo đường đặc tính I-V chuỗi pin': 'PV string I-V curve tracer',
    'Máy đo rung cầm tay': 'Handheld vibration meter',
    'Máy phát thay thế — 6,24 MW': 'Replacement generator — 6.24 MW',
    'Máy toàn đạc điện tử': 'Electronic total station',
    'Mỡ bôi trơn ổ trục — xô 18 kg': 'Bearing grease — 18 kg pail',
    'Mô-đun IGBT biến tần — 1.250 kVA': 'Inverter IGBT module — 1,250 kVA',
    'Mô-tơ hệ xoay kèm hộp giảm tốc': 'Tracker motor with gearbox',
    'Mô-tơ yaw kèm hộp giảm tốc': 'Yaw motor with gearbox',
    'Ổ trục chính (main bearing)': 'Main bearing',
    'Quạt làm mát tủ biến tần': 'Inverter cabinet cooling fan',
    'Rơ-le bảo vệ khoảng cách — dự phòng': 'Distance protection relay — spare',
    'Switch quang công nghiệp 8 cổng': 'Industrial fibre switch, 8 ports',
    'Tấm pin quang điện thay thế — 550 Wp': 'Replacement PV module — 550 Wp',
    'Tư vấn giám sát độc lập (OE) — giai đoạn thi công':
        "Owner's engineer (OE) — construction phase",
    'Văn phòng ban QLDA, xe và hậu cần — 14 tháng':
        'Project management office, vehicles and logistics — 14 months',
    'Vòng trượt (slip ring)': 'Slip ring',
    # ---- hậu tố điểm đo ----
    'Công suất AC toàn nhà máy — theo giờ': 'Plant AC power — hourly',
    # diễn giải luật cảnh báo
    'Kiểm ĐƯỜNG TRUYỀN trước: bộ thu thập, cáp mạng, nguồn. Chỉ ra trụ khi '
    'đã loại trừ phía truyền thông.':
        'Check the COMMUNICATION PATH first: data logger, network cable, '
        'power supply. Only go out to the tower once the comms side has '
        'been ruled out.',
    'Số đọc vẫn về mà giờ chạy không tăng: máy dừng thật. Ra hiện trường.':
        'Readings still arrive but the run hours are not increasing: the '
        'machine really is stopped. Go to site.',
    'Số vẫn về đều nhưng giá trị không đổi suốt ba giờ. Khác hẳn mất tín '
    'hiệu, và hai chuyện ấy sửa ở hai nơi khác nhau.':
        'Readings keep arriving but the value has not changed for three '
        'hours. Quite different from a lost signal, and the two are fixed '
        'in different places.',
    'Cảnh báo quan trọng nhất của một hệ SCADA. Điểm đo im lặng trông giống '
    'hệt điểm đo bình thường trên mọi màn hình — biểu đồ vẫn vẽ tới mốc '
    'cuối, số cuối vẫn hiện. Và trong lúc nó im, MỌI luật ngưỡng canh trên '
    'chính nó cũng im theo.':
        'The most important alarm in a SCADA system. A silent tag looks '
        'exactly like a healthy one on every screen — the chart still draws '
        'to the last point, the last value is still shown. And while it is '
        'silent, EVERY threshold rule watching that tag is silent too.',
    'Hộp số nóng dần là dấu hiệu sớm của hỏng vòng bi hoặc thiếu dầu. Đòi '
    'VƯỢT LIÊN TỤC MỘT GIỜ: một nhịp nhiễu đo cũng chạm ngưỡng, và báo giả '
    'là cách nhanh nhất khiến người ta tắt cả bộ cảnh báo.':
        'A gearbox warming up is an early sign of bearing damage or low '
        'oil. Requires the threshold to be EXCEEDED CONTINUOUSLY FOR ONE '
        'HOUR: a single noisy sample also crosses it, and false alarms are '
        'the fastest way to get the whole alarm system switched off.',
    'Quá LẠNH cũng là chuyện: dầu đặc thì bôi trơn kém. Khai hai luật riêng '
    'cho hai chiều thì hai lần phải sửa khi đổi ngưỡng.':
        'Too COLD matters too: thick oil lubricates poorly. Declaring two '
        'separate rules for the two directions means fixing things twice '
        'whenever the threshold changes.',
    'Một cảm biến trôi dần không tự nói ra — số nó báo vẫn nằm trong dải hợp '
    'lý. Chỉ khi đặt cạnh cảm biến thứ hai mới thấy. Ngưỡng 20% vì hai trụ '
    'cách nhau thì gió vốn đã khác nhau.':
        'A slowly drifting sensor does not announce itself — the value it '
        'reports still sits in a plausible range. It only shows up next to '
        'a second sensor. The threshold is 20% because two towers apart '
        'already see genuinely different wind.',
}


# Hậu tố điểm đo — gốc từ tra ở BẢNG GOC, chỉ thay phần đuôi.
DUOI = {
    ' — cột khí tượng': ' — met mast',
    ' — trạm khí tượng': ' — weather station',
}

def dich(s):
    s = (s or '').strip()
    if not s:
        return None
    if s in NGUYEN:
        return NGUYEN[s]
    for rx, thay in MAU:
        if rx.match(s):
            return rx.sub(thay, s)
    m = CANH.match(s)
    if m:
        return 'Blade %s %s' % (m.group(1), m.group(2))
    if s in GOC:
        return GOC[s]
    m = MA_DUOI.match(s)
    if m:
        g = m.group('goc').strip()
        if g in GOC:
            return GOC[g] + m.group('ma')
    for hv, ha in DUOI.items():
        if s.endswith(hv):
            g = s[:-len(hv)].strip()
            if g in GOC:
                return GOC[g] + ha
    # 'Điện năng luỹ kế — trạm 3' : gốc + ' — trạm <số>'
    m2 = re.match(r'^(.*?) — trạm (\d+)$', s)
    if m2 and m2.group(1) in GOC:
        return '%s — station %s' % (GOC[m2.group(1)], m2.group(2))
    # danh sách tên gọi khác: "Inverter, Converter, Biến tần, Bộ nghịch lưu"
    if ',' in s:
        phan = [p.strip() for p in s.split(',')]
        if all((p in GOC) or not VIET.search(p) for p in phan):
            return ', '.join(GOC.get(p, p) for p in phan)
    return None


DONG = [l for l in open('/var/lib/odoo/con_viet.tsv', encoding='utf-8')
        if l.startswith('T\t')]
dat = bo = 0
chua = {}
de_doi = {}
for l in DONG:
    p = l.rstrip('\n').split('\t')
    if len(p) < 6:
        continue
    mn, rid, col, tr, val = p[1], int(p[2]), p[3], p[4], p[5]
    if mn in BO_MODEL or col in BO_COT or (mn, col) in BO_KHOA:
        bo += 1
        continue
    en = dich(val)
    if not en:
        chua.setdefault(val, 0)
        chua[val] += 1
        continue
    try:
        r = env[mn].with_context(active_test=False).browse(rid)
        if not r.exists():
            continue
        if tr == 'T':
            r.with_context(lang='en_GB').write({col: en})
        else:
            r.write({col: en})           # không dịch được → ghi đè
            de_doi.setdefault('%s.%s' % (mn, col), 0)
            de_doi['%s.%s' % (mn, col)] += 1
        dat += 1
    except Exception as ex:
        print('!! %s#%s.%s: %s' % (mn, rid, col, str(ex)[:80]))

env.cr.commit()
print('ĐÃ ĐẶT %d ô · bỏ qua %d ô (vết tính toán) · chưa khớp %d chuỗi (%d ô)'
      % (dat, bo, len(chua), sum(chua.values())))
print('--- trường KHÔNG dịch được nên phải ghi đè (mất bản tiếng Việt):')
for k, n in sorted(de_doi.items(), key=lambda x: -x[1]):
    print('   %-40s %d ô' % (k, n))
print('--- chuỗi CHƯA khớp, nhiều nhất trước:')
for s, n in sorted(chua.items(), key=lambda x: -x[1])[:40]:
    print('   %4d  %s' % (n, s[:92]))
