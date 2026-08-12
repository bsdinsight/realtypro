# Module Quản lý Vay — Giới thiệu cho tổng thầu

> Tài liệu giới thiệu giải pháp **Quản lý vay vốn** dành cho doanh nghiệp
> xây dựng / tổng thầu / chủ đầu tư trên nền tảng **Realty Pro** (Odoo 19).
> Viết bởi BSDInsight — IP độc quyền, clean-room implementation.

---

## 1. Mục tiêu

Số hoá toàn bộ vòng đời vay vốn của doanh nghiệp xây dựng — từ khi
ký **Hợp đồng tín dụng** với ngân hàng, cấp **hạn mức** cho từng mục
đích sử dụng vốn, rút **Khế ước nhận nợ**, giải ngân, theo dõi lãi,
trả nợ, cho đến đối chiếu sổ sách kế toán theo VAS (Thông tư 200).

**Giá trị mang lại:**

- 📊 **Trực quan dòng tiền vay**: dashboard dư nợ theo NH, theo dự án,
  theo gói thầu — KTT/CFO nắm tình hình tài chính tức thì.
- 🔒 **Kiểm soát hạn mức**: hệ thống TỰ ĐỘNG chặn rút vượt hạn mức,
  cảnh báo sắp đáo hạn, phát hiện KW quá hạn theo aging bucket.
- 🧮 **Tính lãi chính xác**: thuật toán tính lãi pluggable
  (dư nợ giảm dần / cố định), quy ước ngày (Act/360 — chuẩn NH VN).
- 🏗️ **Phân bổ công trình theo VAS §54**: lãi vay capitalize tự
  động vào TK 241 — XDCB dở dang theo dự án / hạng mục / gói thầu.
- 📑 **Báo cáo VN-style sẵn dùng**: 5 mẫu báo cáo nội bộ phục vụ
  KTT, ban tài chính, BLĐ và kiểm toán.

---

## 2. Phạm vi nghiệp vụ

### 2.1 Cấu trúc dữ liệu lõi

```
Hợp đồng tín dụng (HĐTD)
  │  — Master Credit Agreement ký với NH
  │  — Tổng hạn mức, ngày hiệu lực, hết hạn
  │
  ├── Hạn mức tín dụng (Facility) [1..n]
  │   │  — Sub-limit theo mục đích sử dụng vốn
  │   │  — Loại: Tuần hoàn / Có kỳ hạn / Thấu chi / Bảo lãnh / L/C
  │   │  — Mục đích: Vốn lưu động / Đầu tư DH / Bảo lãnh / L/C / ...
  │   │  — Lãi suất mặc định, phương pháp tính lãi, quy ước ngày
  │   │  — ⚙️ Hạn mức liên thông (per-facility): chia pool với facility
  │   │     khác cùng tick liên thông (vd Bảo lãnh ↔ Vay đầu tư)
  │   │
  │   └── Khế ước nhận nợ (KW) [1..n]
  │       │  — Promissory Note / Drawdown
  │       │  — Mỗi lần rút vốn = 1 KW
  │       │  — Số tiền, lãi suất, kỳ hạn riêng
  │       │  — Kế hoạch trả gốc: Bullet / Đều / Tuỳ chỉnh
  │       │
  │       ├── Giải ngân [1..n]         — Tracking từng đợt rút tiền
  │       ├── Lịch lãi [auto]          — Sinh tự động theo phương pháp
  │       ├── Trả nợ (gốc + lãi)       — Lifecycle Trả 1 phần → Tất toán
  │       ├── Phụ lục (Amendment)      — Đổi lãi suất, gia hạn, ...
  │       ├── Tài sản thế chấp         — Multi-pledge, 1 TS bảo đảm n KW
  │       └── Phân bổ công trình       — Theo dự án / hạng mục / gói thầu
  │
  └── Tài sản thế chấp (Collateral)
      — Đăng ký 1 lần, gắn nhiều KW (multi-pledge)
      — Loại: BĐS / Phương tiện / Máy móc / Hàng tồn kho / ...
```

### 2.2 Vai trò người dùng

| Vai trò | Quyền chính |
|---|---|
| **Cán bộ tín dụng** | Tạo & duy trì HĐTD / Facility / KW. Theo dõi giải ngân, trả nợ. |
| **Kế toán** | Đối chiếu KW với sổ NH, hạch toán giải ngân / lãi / trả nợ. Capitalize lãi vay. |
| **Giám đốc tài chính** | Dashboard dư nợ, báo cáo VAS, phê duyệt hạn mức. |
| **Quản lý dự án** | Phân bổ vay & lãi vay theo công trình / gói thầu. |

---

## 3. Tính năng nổi bật

### 3.1 Hợp đồng tín dụng & Hạn mức (Facility)

- **Đa hạn mức theo mục đích**: 1 HĐTD có thể chia thành nhiều facility
  với mục đích khác nhau (Vốn lưu động, Đầu tư dự án, Bảo lãnh, L/C, ...).
- **Hạn mức liên thông per-facility**: tick check box trên từng facility
  để cho phép chia pool. Ví dụ:
  > HĐTD 100 tỷ ⇒ Vay đầu tư 60 tỷ (✓ liên thông) + Bảo lãnh 30 tỷ
  > (✓ liên thông) + L/C 10 tỷ (✗ cố định). Pool liên thông = 90 tỷ
  > dùng chung; L/C giữ 10 tỷ riêng.
- **Phân bổ HĐTD theo dự án × mục đích**: facility có thể phân bổ
  hạn mức cho từng dự án (giúp BGĐ kiểm soát: "Dự án A được dùng
  bao nhiêu hạn mức của HĐTD này").
- **Σ limit luôn ≤ HĐTD**: hard rule, hệ thống chặn cấu hình sai.
- **Validate ngày**: tự động chặn ngày hết hạn < ngày hiệu lực.

### 3.2 Khế ước nhận nợ (KW) — entity lõi

- **Auto-fill từ Facility**: chọn facility xong, KW tự lấy lãi suất,
  phương pháp tính lãi, quy ước ngày làm mặc định (user vẫn override).
- **State machine rõ ràng**: Nháp → Hiệu lực → Trả 1 phần → Tất toán.
  Có thể huỷ (giữ vết) thay vì xoá.
- **Validate số tiền KW**: chặn nhập amount > Còn lại của facility.
  Báo lỗi tiếng Việt cụ thể với gợi ý hành động.
- **Đa loại khoản vay**:
  - **Vay ngân hàng** (external) — chuẩn
  - **Cho vay nội bộ** (onlending) — công ty mẹ cho công ty con vay
    lại từ KW vay NH gốc
- **Đối tác**: lấy từ Facility (NH cho vay) — hoặc Bên vay với onlending.

### 3.3 Giải ngân (Disbursement)

- **Multi-tranche**: 1 KW có nhiều đợt giải ngân theo tiến độ dự án.
- **Liên kết kế toán**: mỗi disbursement có thể link tới `account.move`
  (chứng từ chi tiền NH → TK 1121).
- **Gắn dự án + loại chi phí**: mỗi đợt giải ngân ghi nhận đang dùng
  cho dự án nào, loại chi phí gì (Vd 1.2.3 — Móng), HĐ nhà thầu nào
  (rp.contract). Phục vụ báo cáo dòng tiền theo công trình.

### 3.4 Lịch lãi (Interest Schedule)

- **Sinh tự động** từ ngày nhận nợ + kỳ hạn + phương pháp:
  - **Dư nợ giảm dần** (declining) — chuẩn, dư nợ đầu kỳ × lãi suất × hệ số ngày
  - **Cố định trên gốc ban đầu** (flat) — phổ biến với khoản ngắn hạn
- **Quy ước ngày tính lãi**: Act/360 (default — chuẩn NH VN),
  Act/365, 30/360.
- **Tiền gốc phải trả mỗi kỳ** — tự tính theo Kế hoạch trả gốc:
  - **Trả gốc cuối kỳ (Bullet)**: kỳ cuối = full gốc, các kỳ khác = 0
  - **Trả gốc đều**: mỗi kỳ = amount / số kỳ
  - **Tuỳ chỉnh**: user nhập tay từng dòng (vd theo lịch nhà thầu)
- **Tổng phải trả mỗi kỳ** = gốc + lãi → sum row giúp dự báo dòng tiền
  từng tháng.
- **Sửa tay từng dòng**: NH tính lệch do quy ước ngày → bật cờ
  "Sửa tay" để nhập tiền lãi thực NH thu.
- **Bảo toàn dữ liệu**: regenerate giữ lại dòng đã ghi nhận / đã trả.

### 3.5 Trả nợ & Khôi phục hạn mức

- **Trả gốc + lãi tách bạch**: ghi nhận đúng phần gốc / phần lãi,
  state KW auto chuyển Trả 1 phần / Tất toán.
- **Khôi phục hạn mức (Revolving)**: facility loại Tuần hoàn / Thấu chi
  → khi KW trả gốc, hạn mức TỰ ĐỘNG khôi phục.
  > Vd Facility 10 tỷ revolving, KW vay 2 tỷ → còn 8 tỷ. Trả gốc 1 tỷ
  > → còn 9 tỷ (tự cập nhật, không thao tác thủ công).
- **Term / Bảo lãnh / L/C KHÔNG khôi phục** — đã rút là chiếm đến hết kỳ.
  UI hiển thị badge xanh / xám rõ ràng cho từng loại.

### 3.6 Phụ lục (Amendment)

- **3 loại phụ lục**:
  - **Gia hạn**: đẩy ngày đáo hạn — lịch lãi regen các kỳ chưa ghi nhận
  - **Đổi lãi suất**: áp dụng TỪ ngày hiệu lực phụ lục (KHÔNG retroactive)
    — bảo toàn lãi đã ghi nhận kỳ trước
  - **Đổi điều khoản khác**: ghi nhận, không tự sửa lịch
- **Audit trail đầy đủ**: giá trị cũ → giá trị mới, người ký, ngày ký,
  có chatter để đính kèm file phụ lục PDF.

### 3.7 Tài sản thế chấp (Multi-pledge)

- **Đăng ký 1 lần**: 1 tài sản (BĐS, máy móc, ...) đăng ký vào hệ thống.
- **Bảo đảm nhiều KW**: 1 TS có thể pledge cho n KW (multi-pledge —
  phổ biến với BĐS giá trị lớn bảo đảm nhiều khoản vay).
- **Tổng đảm bảo**: hệ thống tự tổng hợp `total_secured` cho TS đó.
- **Loại tài sản**: master data có sẵn (BĐS / Phương tiện / Máy / ...).

### 3.8 Vay nội bộ (Intercompany On-lending)

- **Kịch bản**: Công ty mẹ vay NH → cho công ty con vay lại với điều
  khoản nội bộ riêng (lãi suất / kỳ hạn khác).
- **Liên kết KW gốc**: tracking dòng tiền 2 cấp, đối chiếu thuận tiện
  với hồ sơ thuế khi auditor hỏi.

### 3.9 Phân bổ công trình (rp_loan_bridge — module cầu nối)

- **Hạt mịn cao**: phân bổ KW (gốc / lãi / cả hai) theo:
  - Dự án (re.project)
  - Hạng mục (rp.structure — Móng, Thân, Hoàn thiện, ...)
  - Nhóm chi phí (rp.cost.category — vd 9.1 "Lãi vay capitalize")
  - Gói thầu (rp.tender.package)
  - HĐ nhà thầu (rp.contract)
- **Phương pháp phân bổ**: theo %, theo số tiền.
- **Capitalize lãi vay theo VAS §54**: lãi vay phục vụ dự án đủ điều
  kiện ghi nhận vào TK 241 (XDCB dở dang) thay vì TK 635 (CP tài chính).
- **Báo cáo**: dư nợ / chi phí lãi theo dự án / hạng mục / gói thầu.

### 3.10 Tích hợp kế toán (re_loan_account — module bridge)

- **Định khoản tự động** theo VAS TT 200:
  - **Giải ngân**: Nợ TK 1121 / Có TK 3411 (vay ngắn hạn) hoặc 3412 (dài hạn)
  - **Ghi nhận lãi (accrual)**: Nợ TK 635 hoặc 241 (capitalize) / Có TK 33531
  - **Trả nợ gốc**: Nợ TK 3411/3412 / Có TK 1121
  - **Trả lãi**: Nợ TK 33531 / Có TK 1121
- **Cấu hình tài khoản** trong **Cài đặt** (per company).
- **Đối chiếu KW ↔ account.move**: trên KW form thấy ngay các bút toán,
  click để xem chi tiết.
- **Cấu hình capitalize**: bật/tắt capitalize theo dự án (TT 200 §54).

---

## 4. Báo cáo (5 mẫu sẵn dùng)

Tất cả báo cáo có filter theo khoảng thời gian, NH, dự án, công ty.
Export Excel / PDF.

| # | Báo cáo | Mục đích |
|---|---|---|
| 1 | **Bảng kê chứng từ theo KW** | Liệt kê đầy đủ giải ngân / trả nợ / lãi của từng KW — phục vụ đối chiếu sổ NH |
| 2 | **Bảng kê đối chiếu KW vay** | Đối chiếu dư nợ KW theo sổ kế toán vs sổ NH — giúp KTT đóng kỳ |
| 3 | **Tổng hợp phát sinh theo KW** | Tổng giải ngân / trả gốc / trả lãi / dư cuối kỳ — báo cáo BLĐ |
| 4 | **Bảng kê quá hạn (Aging)** | Phân loại KW theo aging bucket (trong hạn / 1-30 / 31-60 / 61-90 / >90 ngày) — cảnh báo rủi ro |
| 5 | **Tiến độ thanh toán** | KW + tiến độ giải ngân vs kế hoạch — phục vụ quản lý dòng tiền |

> _Báo cáo VAS S35-DN (Sổ chi tiết tiền vay) hiện đã được XBoss xử lý
> ở tầng kế toán chính — module này không trùng lặp._

---

## 5. Cron tự động (Background jobs)

| Cron | Tần suất | Tác dụng |
|---|---|---|
| Phân loại quá hạn | Hàng ngày | Cập nhật `aging_bucket` cho KW: trong hạn / 1-30 / 31-60 / 61-90 / >90 |
| Nhắc đáo hạn | Hàng ngày | KW sắp đáo hạn trong N ngày → tạo activity cho cán bộ tín dụng |

Cấu hình N ngày, gửi mail / activity tuỳ team.

---

## 6. Kiến trúc module

```
re_loan                          (FOUNDATION — module này)
  ├── re_loan_account            (Bridge kế toán VAS TT 200)
  └── rp_loan_bridge             (Bridge với Realty Project — phân bổ công trình)

re_party                         (Dependency — extend res.partner với is_bank, ...)
re_base                          (Dependency — re.project, re.subzone, ...)
rp_contract / rp_estimate        (Dependency — chỉ với rp_loan_bridge)
```

- **`re_loan`**: foundation độc lập, có thể dùng cho mọi DN — không
  ràng buộc dự án bất động sản.
- **`re_loan_account`**: thêm khi cần định khoản tự động.
- **`rp_loan_bridge`**: thêm khi DN dùng cả Realty Project và muốn
  phân bổ vay theo công trình.

> Cài đặt linh động: KH chỉ Loan thì cài `re_loan` thôi. KH có project
> thì cài thêm bridge. KH muốn auto-accounting thì cài thêm
> `re_loan_account`.

---

## 7. Tuân thủ pháp lý

- **VAS TT 200/2014/TT-BTC**: định khoản TK 1121, 3411, 3412, 33531,
  635, 241 đúng chuẩn.
- **TT 200 §54**: hỗ trợ capitalize lãi vay vào giá thành công trình.
- **Quy ước ngày tính lãi**: theo NHNN — Act/360 mặc định.
- **Audit trail**: chatter đầy đủ trên HĐTD / Facility / KW / Phụ lục
  / Trả nợ.
- **Multi-currency**: kiến trúc sẵn sàng, hiện default VND (theo yêu cầu
  doanh nghiệp xây dựng VN).

---

## 8. Thông số kỹ thuật

| Mục | Chi tiết |
|---|---|
| Nền tảng | **Odoo 19 Community** (open-source — không tốn license/user) |
| Database | **PostgreSQL 16** |
| Ngôn ngữ | **Tiếng Việt** (UI + báo cáo + chứng từ) |
| Hosting | **On-premise** hoặc **Cloud** (KH chọn) |
| Multi-company | Có |
| Multi-currency | Sẵn sàng, hiện set VND |
| Bảo mật | Group-based ACL, audit trail per record, không có hardcoded credentials |
| IP | **BSDInsight độc quyền** — clean-room implementation, không phụ thuộc Viindoo / OCA |

---

## 9. Lộ trình triển khai (gợi ý)

| Tuần | Hoạt động |
|---|---|
| 1 | Khảo sát quy trình hiện tại của tài liệu nghiệp vụ, mapping với module |
| 2 | Cấu hình master data: NH, loại tài sản, tài khoản hạch toán |
| 3 | Import HĐTD đang hiệu lực + Facility + KW dư nợ ban đầu |
| 4 | Đào tạo cán bộ tín dụng + kế toán (1-2 buổi) |
| 5 | Go-live pilot 1 chi nhánh, theo dõi 1 chu kỳ trả lãi |
| 6+ | Rollout toàn DN, mở thêm rp_loan_bridge / re_loan_account nếu cần |

---

## 10. Liên hệ

**BSDInsight Vietnam**
🌐 [https://bsdinsight.com](https://bsdinsight.com)
✉️ daibt@bsdinsight.com

> Module này là **IP độc quyền của BSDInsight**, được viết clean-room
> từ thiết kế nghiệp vụ chuẩn ngân hàng Việt Nam — không sao chép code
> bất kỳ thư viện thương mại nào. tổng thầu sở hữu license sử dụng vô thời hạn
> sau khi triển khai.

---

_Tài liệu cập nhật: 05/2026 — Module phiên bản `19.0.1.18.0`._
