# Yêu cầu thiết kế — Landing page **Realty Pro Network**

> Gửi: session **Claude Design** · Người yêu cầu: anh Đại (BSD) · Ngày: 2026-07-16
> Deliverable: **HTML + CSS self-contained** (sẽ nhúng vào Odoo QWeb — đọc kỹ mục 6)

---

## 1. Bối cảnh & mục tiêu

**Realty Pro Network** (`https://network.realtypro.vn`) là **sàn đấu thầu ngành xây dựng**, kết nối:

- **Tổng thầu** (bên mời thầu) — công bố gói thầu lên Network
- **Nhà thầu phụ / nhà cung cấp thi công** (bên dự thầu) — tìm gói, nộp hồ sơ dự thầu online

Backend đã chạy (Odoo): công bố gói thầu, mời thầu, hồ sơ năng lực, nộp HSDT, chấm thầu. **Đang thiếu duy nhất bộ mặt tiền** — nhà thầu lạ vào chỉ thấy màn hình đăng nhập ERP nên bỏ đi.

**Mục tiêu số 1 của landing: thuyết phục NHÀ THẦU đăng ký tài khoản.** Phụ: gây tin cậy với tổng thầu.

**Ngôn ngữ: Tiếng Việt 100%** (có dấu, UTF-8).

## 2. Đối tượng đọc

- **Chính — Nhà thầu phụ VN**: chủ doanh nghiệp / phòng đấu thầu. Thực dụng, hoài nghi. Câu hỏi trong đầu họ: *"Có gói thật không? Mất phí không? Nộp hồ sơ có rườm rà không? Ai xem được hồ sơ của tôi?"*
- Phụ — **Tổng thầu**: cần thấy sàn nghiêm túc, có nhà thầu thật.

## 3. Thông điệp cốt lõi

1. **Tiếp cận gói thầu thật** từ các tổng thầu trên Network.
2. **Hồ sơ năng lực khai 1 lần — dùng cho mọi gói** (không phải làm lại mỗi lần dự thầu).
3. **Nộp hồ sơ online, có biên nhận** — không giấy tờ, không chạy đi nộp.
4. **Minh bạch**: biết mình được mời / được duyệt / đã nộp / kết quả.

## 4. Các trang cần thiết kế

### 4.1 Landing `/` — ƯU TIÊN CAO NHẤT

| # | Section | Nội dung |
|---|---|---|
| 1 | **Hero** | Tiêu đề + phụ đề + **2 CTA**: `Đăng ký làm nhà thầu` (primary) · `Xem gói thầu đang mời` (secondary) |
| 2 | **Dải số liệu** | 3 số: gói thầu đang mời · nhà thầu · tổng thầu → **để placeholder, KHÔNG bịa số** |
| 3 | **Cách hoạt động — 3 bước** | ① Đăng ký bằng **Mã số thuế** → ② Khai **hồ sơ năng lực** 1 lần → ③ **Đăng ký tham gia gói** & nộp HSDT online |
| 4 | **Gói thầu đang mời** | Preview 3–6 card + link sang `/goi-thau`. Xem mục 4.2 về trường dữ liệu |
| 5 | **Lợi ích cho nhà thầu** | 3–4 ý, bám mục 3 |
| 6 | **Dành cho Tổng thầu** | Băng nhỏ: mời thầu · so sánh · chấm thầu → CTA `Liên hệ` |
| 7 | **FAQ** | Xem mục 5 — phải trả lời được câu "đăng ký xong có xem gói ngay không?" |
| 8 | **Footer** | Liên hệ, điều khoản, chính sách bảo mật |

### 4.2 Trang danh sách gói thầu công khai `/goi-thau`

**Không cần đăng nhập** — đây là mồi câu nhà thầu.

**Trường dữ liệu CÓ THẬT (chỉ dùng đúng những trường này):**

- `Tên gói thầu`
- `Tổng thầu` (tên công ty mời thầu)
- `Chuyên môn` (vd: Cơ điện MEP, Xây lắp, Hạ tầng…)
- `Mô tả / phạm vi` (đoạn ngắn)
- `Ngày mở`
- `Hạn nộp hồ sơ` ← nên làm nổi bật / đếm ngược

> ⚠️ **`Khu vực/Địa điểm` hiện CHƯA có trong dữ liệu.** Nếu thiết kế cần, hãy để **tuỳ chọn** — sẽ bổ sung field sau. Đừng làm bộ lọc phụ thuộc hoàn toàn vào nó.

**Cần có:** bộ lọc (chuyên môn, hạn nộp), nút `Đăng ký tham gia` mỗi card, **trạng thái rỗng** (chưa có gói nào).

> 🚫 **TUYỆT ĐỐI KHÔNG hiện GIÁ GÓI THẦU** (bí mật thương mại — anh Đại đã chốt).
> 🚫 **Không hiện hồ sơ mời thầu (dossier)** — chỉ mở sau khi được duyệt/được mời.

### 4.3 Form đăng ký nhà thầu `/dang-ky`

| Trường | Ghi chú |
|---|---|
| **Tên công ty** | bắt buộc |
| **Mã số thuế (MST)** | bắt buộc — **đây là ID công ty**. Định dạng VN: **10 số**, hoặc **13 ký tự** dạng `xxxxxxxxxx-xxx` (chi nhánh) |
| Người liên hệ | họ tên |
| Email | = tài khoản đăng nhập |
| Điện thoại | |
| Mật khẩu | + xác nhận |
| Đồng ý điều khoản | checkbox |

**Trạng thái LỖI quan trọng — phải thiết kế riêng, đây là điểm mấu chốt:**

> **MST đã tồn tại** → thông báo thân thiện, KHÔNG phải lỗi đỏ cụt lủn:
> *"Công ty này đã có tài khoản trên Realty Pro Network. Vui lòng liên hệ quản trị viên tài khoản công ty để được mời tham gia."*
> → kèm nút `Gửi yêu cầu tới quản trị viên công ty`

*(Lý do: 1 công ty = 1 MST = 1 tài khoản gốc. Người đăng ký ĐẦU TIÊN của MST đó là **quản trị viên công ty**; đồng nghiệp vào sau phải được người đó mời.)*

**Trạng thái sau đăng ký thành công**: *"Đã tạo tài khoản — hãy hoàn thiện hồ sơ năng lực để đăng ký tham gia gói thầu."* + thanh **% hoàn thiện hồ sơ**.

### 4.4 Trang lời mời `/loi-moi` *(nếu còn thời gian)*

Nhà thầu bấm link trong email mời → thấy: tên gói + tên tổng thầu + lời mời → CTA `Đăng ký & xem gói thầu`.

## 5. HAI LUỒNG VÀO — phải thể hiện rõ ở FAQ

| Luồng | Cách vào | Quyền |
|---|---|---|
| **① Được mời** | Tổng thầu nhập email nhà thầu → hệ thống gửi email mời → bấm link đăng ký | ✅ **Mở gói ngay**, không cần duyệt |
| **② Tự đăng ký** | Từ landing → đăng ký → khai hồ sơ năng lực → bấm `Đăng ký tham gia` gói | ⏳ **Chờ Tổng thầu của gói đó duyệt** → mới mở dossier + nộp HSDT |

**FAQ bắt buộc trả lời:**
- *"Đăng ký xong tôi xem được hồ sơ mời thầu ngay không?"* → Không. Cần được tổng thầu duyệt, hoặc được mời trực tiếp.
- *"Có mất phí không?"* → (để placeholder, anh Đại quyết sau)
- *"Ai xem được hồ sơ năng lực của tôi?"* → Chỉ tổng thầu của gói bạn đăng ký tham gia.
- *"Bao lâu được duyệt?"* → Tuỳ tổng thầu.
- *"Tôi khai hồ sơ 1 lần dùng được cho nhiều gói không?"* → Có.

## 6. RÀNG BUỘC KỸ THUẬT — bắt buộc tuân thủ

Trang này sẽ được **nhúng vào Odoo QWeb template** (không phải site tĩnh riêng):

1. **HTML + CSS self-contained.** ❌ **KHÔNG dùng CDN ngoài**: không Tailwind CDN, không Google Fonts qua `<link>`, không JS library ngoài. (Odoo có CSP + phải chạy được khi mạng chặn.)
   - Font: dùng **system font stack**. Nếu bắt buộc font riêng → nhúng base64.
   - JS: chỉ vanilla JS inline, tối thiểu.
2. **Prefix mọi class CSS bằng `rpn-`** (vd `.rpn-hero`, `.rpn-card`) để không đụng CSS của Odoo.
3. **Responsive, mobile-first** — nhà thầu VN phần lớn xem trên điện thoại.
4. Phần **"Gói thầu đang mời"**: để **3 card mẫu** + đánh dấu rõ chỗ lặp bằng comment:
   ```html
   <!-- RPN:TENDER_CARD_LOOP_START -->
   ...1 card mẫu...
   <!-- RPN:TENDER_CARD_LOOP_END -->
   ```
   (tôi sẽ thay bằng `t-foreach` QWeb)
5. Tương tự, đánh dấu placeholder số liệu: `<!-- RPN:STAT_TENDERS -->`, `<!-- RPN:STAT_CONTRACTORS -->`, `<!-- RPN:STAT_GCS -->`
6. **Không ảnh có bản quyền / ảnh nặng.** Cần hình → dùng **SVG / gradient / CSS illustration**, hoặc chừa chỗ + ghi chú.
7. Tiếng Việt có dấu, `<meta charset="utf-8">`.

## 7. 🚫 KHÔNG ĐƯỢC CÓ

- ❌ **Không nêu tên/logo khách hàng thật nào** (không tên tổng thầu cụ thể, không case study, không testimonial giả). Chưa được phép công bố tên khách.
- ❌ **Không hiện giá gói thầu** ở bất kỳ đâu công khai.
- ❌ **Không bịa số liệu** (số nhà thầu/gói thầu/tỷ lệ) → dùng placeholder, sẽ bơm số thật.
- ❌ Không hứa hẹn pháp lý ("đảm bảo trúng thầu", "bảo lãnh"…).

## 8. Tông & thương hiệu

- **Tên: Realty Pro Network** (không viết tắt RPN ở phần nhìn thấy được).
- **Tông**: chuyên nghiệp · tin cậy · thực tế "công trường". B2B xây dựng — **không màu mè, không startup-y**.
- **Màu**: hệ Realty Pro dùng tím/indigo (nền Odoo). Đề xuất 1–2 hướng palette hợp ngành xây dựng mà vẫn nối được với portal Odoo phía sau (người dùng đăng nhập xong sẽ thấy giao diện Odoo tím) — tránh cảm giác "2 trang khác nhau".
- Ưu tiên: **rõ ràng > hoa mỹ**. Chữ to, dễ đọc trên điện thoại ngoài công trường.

## 9. Thứ tự ưu tiên nếu thiếu thời gian

1. **Landing `/`** (mục 4.1)
2. **Form đăng ký `/dang-ky`** + trạng thái lỗi MST trùng (mục 4.3) ← mấu chốt nghiệp vụ
3. **Danh sách gói thầu `/goi-thau`** (mục 4.2)
4. Trang lời mời (mục 4.4)
