# Realty Site — Mobile App Hiện trường · Tài liệu Handoff cho Design

> **Người nhận:** đội thiết kế UI/UX (Claude Design)
> **Người gửi:** BSD Insight — Realty Pro (ERP xây dựng trên Odoo)
> **Ngày:** 14/07/2026 · **Trạng thái:** Brief đã duyệt hướng, chờ design concept
> **Đầu ra mong muốn:** bộ concept UI "đẹp long lanh" — design system, key screens, prototype flow cho 4 luồng vàng (mục 5)

---

## 1. Bối cảnh & định vị sản phẩm

**Realty Pro** là ERP xây dựng cho **Chủ đầu tư + Tổng thầu Việt Nam**. Backend (web) đã chạy: lịch thi công Gantt theo WBS, nhật ký thi công, punch list (lỗi & khắc phục), an toàn HSE (kiểm tra / toolbox / sự cố), nghiệm thu khối lượng BBNT, tạm ứng – thanh toán, Trợ lý AI đọc chứng từ (dự toán, báo cáo tiến độ, giấy báo ngân hàng).

**Mobile app = cánh tay hiện trường của ERP** — không phải phần mềm thứ hai. Nhiệm vụ duy nhất: đưa thực tế công trường (ảnh, lỗi, nhật ký, an toàn) vào hệ thống **trong vài giây**, và đưa việc cần xử lý đến đúng người **trong một cú chạm**.

**Câu thần chú của sản phẩm:** *thắng thói quen "chụp ảnh gửi Zalo"*. Hiện tại mọi công trường VN giao tiếp bằng Zalo: ảnh gửi xong là trôi, không gắn hạng mục, không thành hồ sơ. App chỉ thắng nếu: mở nhanh như Zalo, chụp gửi dễ như Zalo, và **hơn Zalo ở chỗ ảnh tự thành hồ sơ pháp lý** (gắn dự án/hạng mục/nhà thầu, đóng dấu giờ + GPS).

### Số liệu nền (đã kiểm chứng ✅)

| Fact | Nguồn |
|---|---|
| **92%** người ngành xây dựng dùng smartphone hằng ngày cho công việc (hơn laptop 83%, tablet 65%) — ổn định từ 2016 | JBKnowledge ConTech Survey 2020 |
| Mobile là **điều kiện mua hàng**: 48% đòi app có sẵn + 41% đòi roadmap mobile; chỉ 10% chấp nhận phần mềm không mobile | JBKnowledge 2020 |
| **Daily reporting (nhật ký) là use-case số 1** kéo mobile usage tại hiện trường; các lý do dùng phổ biến: xem tài liệu dự án 78%, lập hồ sơ/RFI 71%, chấm công 71%, xem bản vẽ 63% | JBKnowledge 2020 |
| Điểm đau lớn nhất của thị trường: **chỉ 5%** có các app tích hợp dữ liệu với nhau, 27% không có app nào tích hợp → app **ERP-native** (dữ liệu chảy thẳng vào tiến độ/thanh toán) là lợi thế cạnh tranh cốt lõi | Construction Dive / JBKnowledge |
| Đối thủ nội địa **FastCons** đã đưa lên mobile: nhật ký thi công, chụp ảnh hiện trường + báo cáo phát sinh, báo cáo khối lượng, phiếu đề nghị vật tư, nhân công, phiếu chi/đề xuất thanh toán → chuẩn thị trường VN không dừng ở "log ảnh" | fastcons.fastwork.vn |

---

## 2. Personas — ai dùng, dùng thế nào

> Nguyên tắc chọn: app phục vụ người **đứng ngoài nắng**, không phục vụ người ngồi bàn. Nghiệp vụ bàn giấy (khái toán, BOQ, đấu thầu, kế toán, master data) **ở lại web**.

### Nhóm dùng hằng ngày — thiết kế cho họ trước

**① Kỹ sư hiện trường / giám sát (CĐT & tổng thầu)** — *người dùng chính*
- Bối cảnh: ngoài trời cả ngày, nắng gắt, tay bẩn/đeo găng, vừa đi vừa dùng một tay, di chuyển liên tục giữa các tầng/phân khu (tầng hầm mất sóng).
- Tần suất: mở app **10–20 lần/ngày, mỗi lần 15–60 giây**.
- Jobs-to-be-done: chụp ảnh ghi nhận hiện trạng → báo lỗi punch tại chỗ → ghi chép cho nhật ký cuối ngày → xem hôm nay đội nào làm gì → cập nhật % công việc.

**② Chỉ huy trưởng công trường / chỉ huy phó**
- Bối cảnh: nửa hiện trường nửa văn phòng container; là người **duyệt**.
- Jobs: xác nhận nhật ký, nắm punch mở/quá hạn theo nhà thầu, nhận cảnh báo sự cố, phân việc nhanh.
- Tần suất: 5–8 lần/ngày, cần **màn hình duyệt một cú chạm**.

**③ Cán bộ an toàn (HSE officer)**
- Jobs: checklist kiểm tra an toàn buổi sáng, ghi toolbox meeting, lập sự cố/near-miss ngay tại chỗ (có ảnh), theo dõi khắc phục.
- Đặc thù: biểu mẫu lặp hằng ngày → **template + tick nhanh** quyết định adoption.

### Nhóm dùng theo vai trò / theo sự kiện (vẫn trong scope đầy đủ)

**④ Tư vấn giám sát (TVGS)** — xác nhận nhật ký, chứng kiến nghiệm thu, đóng punch (nghiệm thu lại), trả lời RFI, duyệt submittal. Là user ngoài công ty → cần phân quyền hẹp theo dự án.
**⑤ Đội trưởng thầu phụ (foreman)** — nhận việc, báo khối lượng, nhận punch được giao & báo đã khắc phục kèm ảnh, gửi RFI, trình submittal. Điện thoại Android giá rẻ, kỹ năng công nghệ thấp nhất trong các persona → UI phải "một nút một việc".
**⑥ Lãnh đạo CĐT / BQLDA (executive)** — **chỉ đọc**: thẻ tóm tắt tiến độ – tiền – an toàn của các dự án + ảnh mới nhất. Đừng nhồi thao tác nhập liệu; nếu tham vọng quá màn hình này sẽ phá cấu trúc app.
**⑦ Tư vấn thiết kế (TVTK)** — vai "khách mời" nhẹ nhất: nhận và **trả lời RFI** (kèm bản vẽ/sketch), duyệt submittal thuộc phạm vi thiết kế — tất cả qua Hộp duyệt + màn RFI, không cần thấy phần còn lại của app. Phân quyền hẹp nhất.

> Ghi chú benchmark *(khả tín, chưa kịp kiểm chứng ⚠️)*: Raken nhắm foreman/superintendent trước; Fieldwire định vị cho field teams adoption nhanh; Procore nhắm lớp quản lý enterprise. Bài học: **app thắng nhờ persona hiện trường, không phải persona quản lý.**

---

## 3. Feature map — phạm vi ĐẦY ĐỦ (21 chức năng, làm tất cả trong một bản thiết kế)

> Không chia phase. Toàn bộ 21 chức năng nằm trong scope design; thứ tự dưới đây là thứ tự **tần suất sử dụng** (trên = dùng nhiều nhất mỗi ngày) để design phân bổ độ chăm chút.

| # | Chức năng | Yêu cầu trải nghiệm / tiền lệ đã kiểm chứng |
|---|---|---|
| 1 | **Chụp ảnh hiện trường** (camera-first) | FAB camera ở mọi màn hình. Chụp → vẽ annotate (mũi tên, khoanh vùng) → gắn Dự án/Hạng mục/HĐ (mặc định thông minh theo lần trước) → **watermark giờ + GPS in vào ảnh** (giá trị hồ sơ pháp lý). Chụp liên tiếp nhiều ảnh 1 lần. |
| 2 | **Punch nhanh** | Từ ảnh vừa chụp → "+Báo lỗi": 3 trường bắt buộc (mô tả — voice-to-text, nhà thầu chịu trách nhiệm, hạn khắc phục) → lưu **≤15 giây**. Vòng đời Mở→Xử lý→Khắc phục→Đóng bằng swipe/nút to. Kanban punch của tôi. |
| 3 | **AI: ảnh + giọng nói → tạo punch** | "Chụp, nói cái mình thấy, hệ tự tạo việc" — OpenSpace Field (09/2025) ship đúng flow này, khách beta báo **giảm 85% thời gian** log lỗi (số vendor — upper bound). Màn xác nhận đề xuất AI trước khi lưu (nguyên tắc AI đề xuất – người duyệt của Realty Pro). |
| 4 | **Nhật ký thi công 3 phút** | Form **copy sẵn từ hôm qua** (nhân lực, máy móc), thời tiết tự điền, đính ảnh đã chụp trong ngày (tự gom theo ngày + công trường), voice-to-text phần vướng mắc → Trình xác nhận. |
| 5 | **AI viết nhật ký** | AI soạn nháp nhật ký từ dữ liệu ngày (ảnh, voice, công việc) — người dùng review rồi trình. Tiền lệ: Procore Daily Log Agent, Raken AI daily summary. |
| 6 | **An toàn HSE** | Checklist theo template (tick Đạt/Không đạt, ảnh vi phạm → tự thành punch); toolbox meeting 1 màn; sự cố/near-miss có ảnh + phân loại. |
| 7 | **Hộp duyệt** | Một màn gom mọi thứ chờ tôi: xác nhận nhật ký, đóng punch, duyệt tạm ứng, duyệt phiếu vật tư. Swipe phải = duyệt, trái = trả lại kèm ghi chú. |
| 8 | **Việc của tôi** (lịch thi công) | Task tuần này theo HĐ (không cần Gantt đầy đủ trên phone — Gantt để web/tablet); cập nhật % bằng slider; xem phụ thuộc trước/sau. |
| 9 | **Chấm công** | Chấm nhanh theo đội tại hiện trường + bảng công tuần. (FastCons VN đã có — thị trường sẽ hỏi.) |
| 10 | **Phiếu đề nghị vật tư** | Lập phiếu tại hiện trường, đính ảnh; theo dõi trạng thái duyệt. (FastCons đã có.) |
| 11 | **BBNT + chữ ký trên thiết bị** | Form nghiệm thu khối lượng + màn ký điện tử tại hiện trường — giá trị pháp lý cao, nối thẳng vào thanh toán. |
| 12 | **Xem bản vẽ + ghim punch lên bản vẽ** | Chuẩn ngành (Fieldwire/PlanGrid): mở bản vẽ, pin lỗi đúng vị trí trên mặt bằng. |
| 13 | **AI đọc ảnh → insight** | Feed ảnh theo ngày + AI tóm tắt tiến độ, cảnh báo an toàn từ ảnh (tiền lệ: Procore photo intelligence). |
| 14 | **Dashboard executive** (read-only) | Thẻ tóm tắt đa dự án: tiến độ – tiền – an toàn + ảnh mới nhất. Tuyệt đối không thao tác nhập. |
| 15 | **Thông báo** | Trung tâm thông báo; push đúng liều — chỉ 4 loại: giao cho tôi / chờ tôi duyệt / punch sắp & quá hạn / sự cố nghiêm trọng. |
| 16 | **Onboarding & đăng nhập** | SĐT + OTP, chọn dự án; ngày đầu chỉ cần biết 1 nút Chụp ảnh. |
| 17 | **Hồ sơ & đồng bộ** | Cài đặt cá nhân + trạng thái sync/hàng đợi offline (luôn thấy "đã lưu máy / đã lên hệ thống"). |
| 18 | **Offline-first & voice-to-text** (năng lực nền, chạy xuyên mọi chức năng) | Xem mục 4.1; voice-to-text ở mọi ô mô tả (tiền lệ: Raken). |
| 19 | **RFI — Phiếu yêu cầu làm rõ** *(tần suất ~nhóm 9–12)* | Nhà thầu/kỹ sư hỏi TVGS/thiết kế/CĐT khi vướng bản vẽ, xung đột thiết kế: tạo RFI kèm ảnh + voice, **hạn trả lời + đồng hồ đếm ngày chờ** (RFI trễ = căn cứ claim tiến độ), cờ *ảnh hưởng chi phí/tiến độ*, chuỗi hỏi–đáp có giá trị hồ sơ. Trả lời RFI xuất hiện trong Hộp duyệt. Lập RFI trên mobile là top use-case ngành (71% — JBKnowledge ✅). |
| 20 | **Chỉ thị công trường (Site Instruction)** | Chiều ngược RFI: CĐT/TVGS ra chỉ thị cho nhà thầu — nội dung, hạn thực hiện, cờ *phát sinh chi phí*; nhà thầu xác nhận đã thực hiện kèm ảnh. |
| 21 | **Trình duyệt (Submittal)** — mẫu vật liệu / shopdrawing | Nhà thầu trình mẫu/bản vẽ chế tạo kèm ảnh + file → TVGS/CĐT duyệt / duyệt có điều kiện / từ chối (trong Hộp duyệt). Sổ theo dõi trạng thái trình duyệt theo HĐ. |

> **Điểm khác biệt của Realty Site so với mọi app rời:** dữ liệu hiện trường chảy **thẳng vào ERP** — punch chặn nghiệm thu/thanh toán, nhật ký nuôi AI đọc tiến độ, % nhảy vào Gantt, không cần tích hợp gì thêm (nhớ: chỉ 5% thị trường có app tích hợp được với nhau).

---

## 4. Nguyên tắc thiết kế & best practices

### 4.1 Offline-first (bắt buộc, quyết định sống còn ở tầng hầm) ✅

- **Queue-and-sync** như Procore: mọi thao tác offline xếp hàng trên máy, tự đẩy khi có sóng, sau sync thì mọi người trong dự án thấy. (✅ Procore support docs)
- **Cache-on-view có chủ đích**: Procore chỉ xem được thứ đã cache — hạn chế này gây bực; hãy chủ động **pre-cache "gói hôm nay"** (việc của tôi, punch của tôi, nhật ký nháp, danh mục hạng mục/nhà thầu của dự án đang mở) mỗi sáng khi còn WiFi/4G.
- **Media để sau**: học Fieldwire "Smart Sync" — mặc định chỉ sync ảnh/file nặng qua WiFi, text/record sync ngay qua 4G; ảnh upload nền + nén trước. (✅ Fieldwire docs)
- Conflict: bản ghi hiện trường chủ yếu là **append** (ảnh, dòng nhật ký, punch mới) → conflict hiếm; với sửa trạng thái dùng last-write-wins + lưu vết chatter. UI phải luôn hiện **trạng thái sync** (đã lưu máy / đã lên hệ thống) — người dùng mất niềm tin ngay lần đầu "tưởng gửi rồi mà mất".

### 4.2 UI ngoài trời & một tay *(chuẩn ngành + kinh nghiệm, không có citation riêng)* ⚠️

- **Nắng gắt**: contrast cao (nền sáng chữ đậm), không dựa vào màu nhạt/xám mảnh; dark mode không phải ưu tiên (ngoài nắng dark mode khó đọc hơn).
- **Găng tay/tay bẩn**: touch target ≥ 48dp, các nút hành động chính ≥ 56dp, đặt trong **thumb zone** (nửa dưới màn hình), bottom navigation, tránh gesture phức tạp (long-press, multi-finger).
- **Một tay khi đang đi**: mọi luồng chính hoàn thành bằng ngón cái; FAB camera giữa bottom bar.
- **Ít chữ, chữ to**: tiếng Việt mộc mạc đúng khẩu ngữ công trường — "Báo lỗi", "Ghi nhật ký", "Chụp ảnh", "Chờ tôi duyệt". Không icon-only: persona 35–55 tuổi cần icon + nhãn.
- **Pin & máy yếu**: Android giá rẻ là mặt bằng chung VN — app nhẹ, không giữ GPS liên tục (chỉ lấy toạ độ lúc chụp), không animation nặng.

### 4.3 Đặc thù Việt Nam ⚠️

- **Đối thủ thật là Zalo, không phải Procore.** Mỗi flow phải trả lời được: "nhanh hơn hay bằng gửi Zalo chưa, và hơn Zalo cái gì?" → câu trả lời thiết kế: *chụp trong app nhanh như Zalo + ảnh tự thành hồ sơ (watermark, gắn hạng mục) + không bao giờ phải gõ lại lần 2*.
- Onboarding: đăng nhập bằng số điện thoại + OTP (không bắt nhớ email/password); video 60 giây; ngày đầu chỉ cần biết 1 nút Chụp ảnh.
- Phân quyền theo dự án/HĐ (TVGS và thầu phụ chỉ thấy phần của mình) — dùng chuẩn quyền Odoo hiện có.

### 4.4 Nền tảng build *(ghi chú kỹ thuật của BSD — không ảnh hưởng công việc design)* ⚠️

- Với phạm vi đầy đủ (offline sâu, hàng đợi media, camera pipeline, voice, push tin cậy, ký điện tử), phương án build là **React Native + Expo (TypeScript)** — đồng bộ toolchain với Sapiones Mobile của BSD (đã chạy quy trình Claude Design HTML → port RN thành công); PWA trên Odoo chỉ đủ cho bản chạy thử nội bộ.
- Yêu cầu cho design: vẽ **mobile-first thuần** theo design system riêng của Realty Site — KHÔNG lệ thuộc look & feel Odoo web; backend Odoo chỉ là nơi dữ liệu đổ về. Bản HTML của design sẽ được port sang React Native (View/Text/Pressable + StyleSheet) như đã làm với Sapiones Mobile.

---

## 5. Bốn "luồng vàng" cần prototype (đo bằng đồng hồ)

| Luồng | Mục tiêu thời gian | Ghi chú |
|---|---|---|
| Mở app → chụp 3 ảnh gắn hạng mục → xong | **≤ 20 giây** | Ngang gửi Zalo |
| Ảnh → punch đầy đủ (mô tả + nhà thầu + hạn) | **≤ 15 giây** sau ảnh | Voice-to-text mô tả |
| Nhật ký cuối ngày (copy hôm qua + sửa) | **≤ 3 phút** | Kể cả đính 10 ảnh |
| Chỉ huy trưởng duyệt 5 mục chờ | **≤ 1 phút** | Swipe trong Hộp duyệt |

**KPI thành công sau triển khai:** % nhật ký lập trên mobile; thời gian trung bình tạo punch; tỷ lệ ảnh công trường vào app (thay vì chỉ Zalo); DAU theo persona; % nhật ký được xác nhận trong 24h.

---

## 5b. Kiểm kê màn hình (screen inventory)

**Tổng phạm vi: 21 chức năng · 39 màn hình — làm tất cả trong một bản thiết kế, không chia phase.**

| Chức năng | Màn hình | SL |
|---|---|---|
| Onboarding & đăng nhập | Nhập SĐT + OTP · Chọn dự án | 2 |
| Home "Hôm nay của tôi" | Dashboard cá nhân (việc + punch + nút lớn) | 1 |
| Chụp ảnh hiện trường | Camera (chụp liên tiếp) · Annotate vẽ trên ảnh · Gắn thẻ dự án/hạng mục/HĐ & lưu | 3 |
| Punch list | Danh sách/kanban punch · Tạo nhanh (3 trường + voice) · Chi tiết punch (vòng đời, ảnh khắc phục, trao đổi) | 3 |
| AI: ảnh + giọng nói → punch | Màn xác nhận đề xuất AI | 1 |
| Nhật ký thi công | Danh sách nhật ký · Soạn nhật ký (sections: công việc/nhân lực/máy/ảnh/ghi chú) · Xem & xác nhận | 3 |
| AI viết nhật ký | Review bản nháp AI trước khi trình | 1 |
| An toàn HSE | Hub an toàn · Thực hiện checklist · Toolbox meeting · Sự cố/near-miss | 4 |
| Hộp duyệt | Danh sách chờ duyệt (swipe duyệt/trả) | 1 |
| Việc của tôi | Lịch tuần theo HĐ + slider % | 1 |
| Chấm công | Chấm nhanh theo đội · Bảng công tuần | 2 |
| Phiếu đề nghị vật tư | Danh sách phiếu · Form đề nghị | 2 |
| BBNT trên thiết bị | Form nghiệm thu · Màn ký điện tử | 2 |
| Xem bản vẽ + pin punch | Danh sách bản vẽ · Viewer + ghim lỗi | 2 |
| AI photo insights | Feed ảnh theo ngày + nhận định AI | 1 |
| Dashboard executive | Thẻ tóm tắt đa dự án (read-only) | 1 |
| RFI — yêu cầu làm rõ | Danh sách RFI (đồng hồ chờ) · Tạo RFI (ảnh + voice) · Chi tiết hỏi–đáp & trả lời | 3 |
| Chỉ thị công trường | Danh sách chỉ thị · Chi tiết + xác nhận thực hiện kèm ảnh | 2 |
| Trình duyệt (Submittal) | Sổ trình duyệt theo HĐ · Chi tiết + duyệt/từ chối | 2 |
| Thông báo | Trung tâm thông báo | 1 |
| Hồ sơ & đồng bộ | Cài đặt cá nhân + trạng thái sync/hàng đợi offline | 1 |

> Ghi chú cho design: cả 39 màn dùng chung **1 design system** (bottom nav 5 tab: Hôm nay · Việc · ➕Camera · Duyệt · Thông báo) nên khối lượng thực tế ≈ 1 hệ thống + 39 biến thể màn hình; các form Odoo phía sau đã có sẵn cấu trúc trường, không cần thiết kế data model. Ưu tiên độ chăm chút theo thứ tự bảng feature map (mục 3) — 4 luồng vàng ở mục 5 vẫn là thước đo chất lượng UX.

## 6. Moodboard & brand hints

- Brand Realty Pro: **teal đậm `#0a3d47`** (đang dùng nhất quán trên web/Gantt), accent hổ phách `#e0a460` (milestone), trạng thái: xanh lá = xác nhận/đóng, vàng = chờ, đỏ = quá hạn/nghiêm trọng.
- Cảm giác cần đạt: **công cụ lao động** — chắc, rõ, nhanh; không phải app lifestyle. Tham khảo độ "gọn mà đẹp" của Raken (daily report) + Fieldwire (task/punch).
- Ngôn ngữ: 100% tiếng Việt, thuật ngữ đúng công trường (nhật ký thi công, punch/lỗi, BBNT, TVGS, tạm ứng).

---

## 7. Phụ lục — mức tin cậy của brief

- **✅ Đã kiểm chứng 3 phiếu độc lập** (18 claim): số liệu JBKnowledge (92% smartphone, 89% dealbreaker, daily report #1, 5% tích hợp), Procore Daily Log Agent + photo intelligence, OpenSpace Field voice-to-punch + 85%, Raken voice-to-text + AI summary + flow work log/time card/checklist, Fieldwire offline editing + Smart Sync, Procore queue-and-sync + cache-on-view, FastCons feature set VN.
- **⚠️ Khả tín nhưng chưa kiểm chứng xong** (bị cắt giữa chừng): định vị persona của Raken/Fieldwire/Procore; bảng xếp hạng workflow mobile phổ biến. Dùng như tham khảo, đừng trích dẫn số.
- **❌ Đã bị bác — không dùng**: "Procore Assist có voice trên mobile" (chưa xác nhận được); "OpenSpace tự pin ảnh lên floorplan bằng Spatial AI thay GPS" (nguồn không đỡ được claim).
- Các mục 4.2, 4.3, 4.4 là chuẩn ngành + phán đoán chuyên môn của BSD, không có citation riêng — Claude Design cứ thoải mái thách thức.

*Nguồn chính: JBKnowledge ConTech Survey 2020 (ashb.com PDF), procore.com/press, openspace.ai/press-releases, rakenapp.com/features/daily-reports, help.fieldwire.com, support.procore.com, fastcons.fastwork.vn, constructiondive.com.*
