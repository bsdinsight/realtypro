# BRD — Quản lý Vay (Loan Management)

**Module**: `re_loan` (Realty Pro — `_common/` foundation)
**Phiên bản tài liệu**: v1.0 (draft)
**Ngày**: 25/05/2026
**Tác giả**: BSDInsight (Claude Code)
**Trạng thái**: Draft — chờ owner review
**Nguồn tham chiếu**:
- `BÁO CÁO KẾ TOÁN TRÊN ODOO.docx` (catalog ~96 báo cáo/biểu mẫu tổng thầu)
- `tổng thầu_scope_v4.xlsx` (scope tổng hợp 82 yêu cầu, 17 module, 71.5 man-week)
- Đối tượng tổng quát hoá: doanh nghiệp xây dựng / tổng thầu / chủ đầu tư

---

## 0. Tóm tắt điều hành (Executive Summary)

Mọi doanh nghiệp xây dựng, tổng thầu, chủ đầu tư đều phải vay vốn ngân hàng để
tài trợ thi công và đầu tư dự án. Nghiệp vụ vay tại Việt Nam xoay quanh **Hợp
đồng tín dụng (HĐTD)** → cấp **hạn mức (facility)** → từng lần rút vốn tạo
**Khế ước nhận nợ (KW)** → theo dõi **giải ngân / lãi / trả gốc-lãi** → thế chấp
bằng **tài sản đảm bảo (collateral)**. Tập đoàn nhiều công ty con còn có nghiệp
vụ **vay nội bộ (on-lending)**: công ty mẹ vay ngân hàng rồi cho công ty con
vay lại.

`re_loan` là module **foundation dùng chung** (đặt tại `addons/_common/`), phục
vụ mọi suite của Realty Pro. Realty Project bổ sung **bridge** để phân bổ gốc/lãi
vay theo công trình (`rp.structure`). Module này **không** ôm trọn gói tài chính
tổng thầu (VAS, treasury reports, biểu mẫu ngân hàng theo từng bank, bảo lãnh/L/C/tiền
gửi) — các phần đó để domain `_finance/` xử lý sau.

---

## 1. Mục đích & phạm vi tài liệu

Tài liệu này mô tả **yêu cầu nghiệp vụ (Business Requirements)** cho module quản
lý vay generic. Đây là cơ sở để:
- Thống nhất scope giữa BSDInsight và chủ dự án trước khi code
- Làm đầu vào cho thiết kế kỹ thuật (data model, view, workflow)
- Làm căn cứ nghiệm thu từng phase

Tài liệu **không** mô tả chi tiết kỹ thuật triển khai (sẽ có ở SDD/Technical
Design riêng).

---

## 2. Bối cảnh nghiệp vụ

### 2.1 Chuỗi vay vốn điển hình tại VN

```
Doanh nghiệp ──ký──► Hợp đồng tín dụng (HĐTD) với Ngân hàng
                          │  (có 1..n hạn mức / facility)
                          ▼
                     Hạn mức tín dụng (Facility)
                          │  (revolving / term / thấu chi / hạn mức BL-LC)
                          ▼
   Mỗi lần cần tiền ──► Khế ước nhận nợ (KW)  ◄── rút vốn trong hạn mức
                          │
            ┌─────────────┼──────────────┬─────────────────┐
            ▼             ▼              ▼                 ▼
        Giải ngân      Lịch lãi       Trả gốc/lãi      Tài sản thế chấp
       (disbursement)  (interest)     (repayment)      (collateral pledge)
                          │
                          ▼
              Lifecycle KW: draft → active → partial_paid
                          → fully_paid / overdue / restructured
```

### 2.2 Vì sao tách "Khế ước nhận nợ" thành entity first-class

1 HĐTD cấp 1 hạn mức (vd 500 tỷ revolving 12 tháng). Doanh nghiệp **rút nhiều
lần**, mỗi lần là 1 KW với: số tiền, lãi suất, kỳ hạn, mục đích sử dụng vốn,
lịch trả riêng. Kế toán/treasury theo dõi **dư nợ, lãi, quá hạn theo từng KW**
chứ không theo HĐTD. Đây là khác biệt cốt lõi so với "loan" đơn giản trong các
ERP nước ngoài (nơi 1 loan = 1 khoản trả góp).

### 2.3 Vay nội bộ (intercompany / on-lending)

Tập đoàn như tài liệu nghiệp vụ: công ty mẹ có quan hệ tín dụng tốt, đứng ra vay ngân hàng
(KW external) rồi **cho công ty con vay lại** (KW on-lending), thường cùng/cao
hơn lãi suất gốc một biên độ. Cần theo dõi đối ứng: 1 khoản vay ngoài tài trợ
cho 1..n khoản cho vay lại; dư nợ mỗi bên độc lập.

---

## 3. Phạm vi (Scope)

### 3.1 Trong phạm vi (IN — BRD v1)

| # | Hạng mục | Mô tả |
|---|---|---|
| IN-1 | HĐTD master | Hợp đồng tín dụng với ngân hàng, hồ sơ, phụ lục |
| IN-2 | Hạn mức (Facility) | Hạn mức con dưới HĐTD; theo dõi limit / đã dùng / còn lại |
| IN-3 | Khế ước nhận nợ (KW) | Entity lõi: rút vốn, lifecycle, lãi, trả nợ, mục đích vốn |
| IN-4 | Giải ngân | Các lần giải ngân thuộc 1 KW |
| IN-5 | Lãi vay | Lịch tính lãi, phương pháp (dư nợ giảm dần / cố định), kỳ tính |
| IN-6 | Trả nợ | Trả gốc + lãi, phân bổ vào KW; cập nhật dư nợ |
| IN-7 | Phụ lục KW | 6 loại: gia hạn, đổi số tiền, đổi lãi suất, đổi mục đích, đổi lịch trả, đổi TS thế chấp |
| IN-8 | Tài sản thế chấp | Master TS, định giá nhiều phương pháp, multi-pledge, giải chấp |
| IN-9 | Vay nội bộ (on-lending) | Cho công ty con vay lại, đối ứng với KW external |
| IN-10 | Phân bổ công trình | Phân bổ gốc/lãi theo `re.project` (generic); bridge sang `rp.structure` ở Realty Project |
| IN-11 | Báo cáo lõi | Dư nợ theo NH/HĐTD/KW, lịch trả nợ sắp đến hạn, theo dõi quá hạn (aging) |
| IN-12 | Cảnh báo đáo hạn | Activity nhắc khi KW/HĐTD/định giá TS sắp đáo hạn |

### 3.2 Ngoài phạm vi (OUT — để domain `_finance/` hoặc phase sau)

| # | Hạng mục | Lý do |
|---|---|---|
| OUT-1 | Báo cáo tài chính VAS (B01/B02/sổ KT…) | XBoss làm |
| OUT-2 | 23 treasury reports đầy đủ | Domain `_finance/rf_treasury_reports` |
| OUT-3 | 17 biểu mẫu NH theo từng bank (UNC VCB/TCB/AGB, KUNN BIDV…) | `_finance/rf_bank_forms` |
| OUT-4 | Bảo lãnh ngân hàng (BL) | `_finance/rf_bank_guarantee` |
| OUT-5 | Thư tín dụng (L/C) | `_finance/rf_letter_of_credit` |
| OUT-6 | Tiền gửi có kỳ hạn (HDTG) | `_finance/rf_time_deposit` |
| OUT-7 | Cam kết tín dụng (TX TC CK) | `_finance/rf_credit_commitment` |
| OUT-8 | COA / branding / migration riêng từng khách | addons riêng của khách |
| OUT-9 | Master data ngân hàng đầy đủ (seed 20+ NH, mã NHNN, template per bank) | `re_bank` (dùng `res.bank` chuẩn cho v1, xem §13) |

### 3.3 Ranh giới với kế toán

`re_loan` quản lý **nghiệp vụ vay** (số liệu, lịch, lifecycle). Việc hạch toán
bút toán (`account.move`) cho giải ngân/lãi/trả nợ là **tùy chọn**: nếu Odoo
Accounting được cài, v2 sẽ sinh bút toán; v1 chỉ ghi nhận số liệu + lịch. Xem §12.

---

## 4. Đối tượng sử dụng & vai trò (Actors & Roles)

| Vai trò | Mô tả | Quyền chính |
|---|---|---|
| **Treasury / Cán bộ vốn** | Quản lý HĐTD, hạn mức, KW, giải ngân, trả nợ | Tạo/sửa toàn bộ nghiệp vụ vay |
| **Kế toán** | Đối chiếu lãi/gốc, hạch toán | Xem + đối chiếu + (v2) post bút toán |
| **Quản lý tài sản** | Quản lý TS thế chấp, định giá, giải chấp | CRUD collateral |
| **Lãnh đạo / Phê duyệt** | Duyệt HĐTD, KW, giải ngân, giải chấp (theo cấp) | Approve/reject |
| **Kế toán công ty con** | Theo dõi khoản vay nội bộ nhận từ cty mẹ | Xem KW on-lending của cty mình |
| **Admin hệ thống** | Cấu hình loại facility, phương pháp lãi, chính sách aging | Configuration |

> Phân quyền chi tiết (groups, record rules theo company) sẽ chốt ở SDD. BRD chỉ
> liệt kê vai trò nghiệp vụ.

---

## 5. Kiến trúc module & vị trí

```
addons/
├── _common/
│   ├── re_party/        (đã có) — extend res.partner; bổ sung is_bank, MST, cty mẹ/con
│   ├── re_base/         (đã có) — re.project (đích phân bổ generic)
│   └── re_loan/         ◄── MODULE MỚI (BRD này)
│             models: re.loan.credit.contract, re.loan.facility,
│                     re.loan.note (+ disbursement/interest/repayment/amendment),
│                     re.loan.collateral (+ valuation/pledge/release),
│                     re.loan.onlending
├── _project/
│   └── rp_loan_bridge/  ◄── BRIDGE (Realty Project) — phân bổ KW ↔ rp.structure,
│                            menu vay trong app Realty Project
```

**Naming convention**: theo `docs/development.md` — module shared dùng prefix
`re_*`, model `re.loan.*`. (Khác `rf_*` của scope v4 vì v4 đặt ở domain
`_finance/` riêng; ở đây ta chọn foundation dùng chung.)

**Phụ thuộc**: `re_loan` depends `['base', 'mail', 're_party', 're_base']`.
Bridge `rp_loan_bridge` depends `['re_loan', 'rp_cost_base']`.

---

## 6. Quy trình nghiệp vụ (Business Processes)

### BP-1: Thiết lập HĐTD & hạn mức

1. Treasury tạo **HĐTD** với ngân hàng: số HĐ, ngày ký, ngày hiệu lực/hết hạn,
   tổng hạn mức, đính kèm hồ sơ.
2. Khai báo 1..n **Facility** dưới HĐTD: loại (revolving / term / thấu chi /
   hạn mức BL-LC), số tiền hạn mức, kỳ hạn, lãi suất tham chiếu.
3. (Tùy chọn) Gắn **tài sản thế chấp** đảm bảo cho HĐTD/facility.
4. Lãnh đạo phê duyệt → HĐTD chuyển `active`.

### BP-2: Rút vốn — tạo Khế ước nhận nợ (KW)

1. Treasury chọn 1 **Facility** còn hạn mức → tạo **KW**: số KW, ngày nhận nợ,
   số tiền, lãi suất, kỳ hạn, mục đích sử dụng vốn, lịch trả dự kiến.
2. Hệ thống kiểm tra **số tiền KW ≤ hạn mức còn lại** của facility.
3. (Tùy chọn) Gắn TS thế chấp riêng cho KW; phân bổ KW theo công trình
   (`re.project` / `rp.structure`).
4. Phê duyệt → KW `active`; **hạn mức đã dùng của facility tăng tương ứng**.

### BP-3: Giải ngân

1. Dưới 1 KW, tạo 1..n bản ghi **Giải ngân**: ngày, số tiền, tài khoản nhận.
2. Tổng giải ngân ≤ số tiền KW.
3. (v2) Sinh bút toán Nợ tiền gửi / Có vay.
4. (Tùy chọn) In Giấy nhận nợ / UNC — *biểu mẫu generic, per-bank để `_finance/`*.

### BP-4: Tính lãi & lập lịch trả

1. Khi KW `active`, hệ thống sinh **lịch lãi** theo phương pháp:
   - Dư nợ giảm dần (lãi tính trên dư nợ thực tế)
   - Lãi cố định trên gốc ban đầu
2. Mỗi kỳ: ngày tính, dư nợ đầu kỳ, số ngày, lãi suất, tiền lãi phải trả.
3. Lịch trả gốc: theo thỏa thuận (cuối kỳ / chia đều / không đều).

### BP-5: Trả nợ

1. Treasury tạo **Trả nợ**: ngày, số tiền gốc, số tiền lãi, KW liên quan.
2. Hệ thống cập nhật **dư nợ KW** = số tiền − tổng gốc đã trả.
3. Lifecycle KW tự cập nhật: còn dư → `partial_paid`; dư = 0 → `fully_paid`;
   quá hạn chưa trả → `overdue`.
4. Khi KW `fully_paid` → **hoàn lại hạn mức** cho facility (nếu revolving).

### BP-6: Phụ lục KW

Treasury tạo **Phụ lục** thuộc 1 trong 6 loại; mỗi phụ lục có hiệu lực từ ngày,
ghi nhận giá trị cũ/mới, đính kèm văn bản:
- Gia hạn kỳ hạn (extension)
- Thay đổi số tiền (amount)
- Thay đổi lãi suất (rate)
- Thay đổi mục đích sử dụng vốn (purpose)
- Thay đổi lịch trả (schedule)
- Thay đổi tài sản thế chấp (collateral)

### BP-7: Quản lý tài sản thế chấp

1. Tạo **TS thế chấp**: loại (BĐS / phương tiện / hàng tồn kho / quyền tài
   sản / cổ phần…), chủ sở hữu (công ty thành viên), thông tin pháp lý.
2. **Định giá** (valuation): nhiều phương pháp, nhiều lần theo thời gian; lưu
   giá trị + ngày + tổ chức định giá.
3. **Thế chấp (pledge)**: gắn TS vào HĐTD/facility/KW. **Multi-pledge**: 1 TS
   có thể đảm bảo nhiều khoản (theo dõi tổng giá trị bảo đảm vs tổng dư nợ).
4. **Giải chấp (release)**: khi khoản vay tất toán, giải phóng TS.

### BP-8: Vay nội bộ (on-lending)

1. Từ 1 **KW external** (cty mẹ vay NH), tạo 1..n **khoản cho vay lại** cho công
   ty con: số tiền, lãi suất (≥ lãi gốc + biên độ), kỳ hạn.
2. Tổng cho vay lại ≤ số tiền KW external.
3. Theo dõi dư nợ on-lending độc lập; cảnh báo nếu lãi cho vay lại < lãi gốc.

---

## 7. Yêu cầu chức năng (Functional Requirements)

### FR nhóm A — HĐTD (Credit Contract)
- FR-A1: CRUD HĐTD với các trường: số HĐ, ngân hàng, ngày ký, hiệu lực, hết hạn,
  tổng hạn mức, loại tiền, công ty vay, người đại diện, ghi chú.
- FR-A2: Quản lý hồ sơ đính kèm (documents).
- FR-A3: Lifecycle HĐTD: `draft → active → expired / closed / cancelled`.
- FR-A4: Tính tổng hạn mức đã cấp cho các facility ≤ tổng hạn mức HĐTD.

### FR nhóm B — Facility (Hạn mức)
- FR-B1: CRUD facility dưới HĐTD: loại, số tiền hạn mức, kỳ hạn, lãi suất tham chiếu.
- FR-B2: Computed: `limit_used` (tổng dư nợ KW active), `limit_available` = limit − used.
- FR-B3: Cảnh báo/khoá tạo KW khi vượt hạn mức còn lại.
- FR-B4: Loại facility: revolving / term / overdraft / guarantee_line / lc_line.

### FR nhóm C — Khế ước nhận nợ (KW) — LÕI
- FR-C1: CRUD KW thuộc 1 facility: số KW, ngày nhận nợ, số tiền, lãi suất, kỳ
  hạn (tháng/ngày), ngày đáo hạn, mục đích sử dụng vốn.
- FR-C2: Lifecycle: `draft → active → partial_paid → fully_paid`; nhánh
  `overdue`, `restructured`, `cancelled`.
- FR-C3: Computed: dư nợ gốc (`principal_outstanding`), tổng lãi phải trả, tổng
  đã trả, ngày trả gần nhất.
- FR-C4: O2M: giải ngân, lịch lãi, trả nợ, phụ lục, phân bổ công trình, pledge.
- FR-C5: Kiểm tra tổng giải ngân ≤ số tiền KW; tổng trả gốc ≤ số tiền KW.
- FR-C6: Đánh dấu `overdue` khi quá ngày đáo hạn mà `principal_outstanding > 0`
  (qua cron).

### FR nhóm D — Giải ngân
- FR-D1: CRUD giải ngân thuộc KW: ngày, số tiền, tài khoản nhận, tham chiếu chứng từ.
- FR-D2: Ràng buộc tổng ≤ số tiền KW.

### FR nhóm E — Lãi vay
- FR-E1: Sinh lịch lãi tự động theo phương pháp (dư nợ giảm dần / cố định) khi KW active.
- FR-E2: Mỗi dòng lãi: kỳ, ngày tính, dư nợ đầu kỳ, số ngày, lãi suất, tiền lãi.
- FR-E3: Cho phép điều chỉnh thủ công 1 dòng lãi (override) khi NH tính khác.

### FR nhóm F — Trả nợ
- FR-F1: CRUD trả nợ: ngày, gốc, lãi, KW, tham chiếu chứng từ.
- FR-F2: Cập nhật dư nợ KW + lifecycle sau mỗi lần trả.
- FR-F3: Revolving: hoàn hạn mức facility khi KW fully_paid.

### FR nhóm G — Phụ lục KW
- FR-G1: CRUD phụ lục với 6 loại; lưu giá trị cũ/mới, ngày hiệu lực, văn bản.
- FR-G2: Áp dụng thay đổi vào KW (vd gia hạn → cập nhật ngày đáo hạn).

### FR nhóm H — Tài sản thế chấp
- FR-H1: CRUD TS thế chấp: loại, chủ sở hữu (company), pháp lý, mô tả.
- FR-H2: Định giá nhiều lần: giá trị, ngày, phương pháp, tổ chức định giá; lấy
  định giá mới nhất làm giá trị hiện hành.
- FR-H3: Pledge: gắn TS ↔ HĐTD/facility/KW; multi-pledge; theo dõi tổng giá trị
  đảm bảo vs tổng dư nợ được đảm bảo.
- FR-H4: Giải chấp: release pledge khi khoản vay tất toán; lịch sử thế chấp.

### FR nhóm I — Vay nội bộ
- FR-I1: Tạo khoản cho vay lại từ KW external → công ty con (borrower).
- FR-I2: Ràng buộc tổng cho vay lại ≤ KW external; cảnh báo lãi cho vay lại < lãi gốc.
- FR-I3: Theo dõi dư nợ on-lending độc lập.

### FR nhóm J — Phân bổ công trình
- FR-J1: Phân bổ KW (gốc và/hoặc lãi) theo `re.project` với % hoặc số tiền; tổng = 100%/số tiền KW.
- FR-J2 (bridge): mở rộng phân bổ tới `rp.structure` / `rp.cost.category` trong Realty Project.

### FR nhóm K — Báo cáo & cảnh báo (lõi)
- FR-K1: Báo cáo **dư nợ** theo Ngân hàng / HĐTD / KW (pivot + list).
- FR-K2: **Lịch trả nợ sắp đến hạn** (gốc + lãi) trong N ngày.
- FR-K3: **Theo dõi quá hạn (aging)** theo bucket cấu hình được (trong hạn,
  1-30, 31-60, 61-90, 91-180, 181-365, >365 ngày).
- FR-K4: Activity nhắc đáo hạn KW / HĐTD / định giá TS (qua cron + mail.activity).
- FR-K5: Export Excel các báo cáo trên.

---

## 8. Mô hình dữ liệu (Data Model — mức khái niệm)

```
re.loan.credit.contract (HĐTD)
   │ 1..n
   ├── re.loan.facility (Hạn mức)
   │       │ 1..n
   │       └── re.loan.note (Khế ước nhận nợ) ◄────────┐
   │               │                                    │
   │               ├── re.loan.note.disbursement        │
   │               ├── re.loan.note.interest.line       │
   │               ├── re.loan.note.repayment           │
   │               ├── re.loan.note.amendment           │
   │               ├── re.loan.note.project.allocation ─┼─► re.project
   │               └── re.loan.onlending ───────────────┘   (borrower = company con)
   │
   └── (pledge) ◄── re.loan.collateral.pledge ──► re.loan.collateral
                                                      │
                                                      ├── re.loan.collateral.valuation
                                                      └── re.loan.collateral.release
```

**Các model chính** (chi tiết trường ở SDD):

| Model | Vai trò |
|---|---|
| `re.loan.credit.contract` | HĐTD master với ngân hàng |
| `re.loan.facility` | Hạn mức con dưới HĐTD |
| `re.loan.note` | Khế ước nhận nợ — entity lõi |
| `re.loan.note.disbursement` | Lần giải ngân |
| `re.loan.note.interest.line` | Dòng lịch lãi |
| `re.loan.note.repayment` | Lần trả gốc/lãi |
| `re.loan.note.amendment` | Phụ lục KW (6 loại) |
| `re.loan.note.project.allocation` | Phân bổ theo `re.project` |
| `re.loan.onlending` | Khoản cho vay lại nội bộ |
| `re.loan.collateral` | Tài sản thế chấp |
| `re.loan.collateral.valuation` | Định giá |
| `re.loan.collateral.pledge` | Quan hệ thế chấp (multi-pledge) |
| `re.loan.collateral.release` | Giải chấp |

> Bridge `rp_loan_bridge` (Realty Project) thêm inherit `rp.structure`
> (add `loan_note_ids`) và model phân bổ chi tiết tới hạng mục/mã phí.

---

## 9. Quy tắc nghiệp vụ (Business Rules)

- BR-1: Tổng hạn mức các facility ≤ tổng hạn mức HĐTD.
- BR-2: Số tiền KW ≤ hạn mức còn lại của facility tại thời điểm tạo.
- BR-3: Tổng giải ngân của 1 KW ≤ số tiền KW.
- BR-4: Tổng trả gốc của 1 KW ≤ số tiền KW.
- BR-5: KW `overdue` khi `ngày hiện tại > ngày đáo hạn` và `dư nợ gốc > 0`.
- BR-6: Revolving facility hoàn hạn mức khi KW `fully_paid`; term facility không hoàn.
- BR-7: Tổng cho vay lại (on-lending) ≤ số tiền KW external nguồn.
- BR-8: Lãi suất cho vay lại nên ≥ lãi suất KW external (cảnh báo, không chặn cứng).
- BR-9: Tổng phân bổ công trình của 1 KW = 100% (nếu theo %) hoặc = số tiền KW (nếu theo tiền).
- BR-10: Không cho xoá HĐTD/facility/KW đã có giao dịch (giải ngân/trả nợ); chỉ huỷ (cancel).
- BR-11: Giải chấp chỉ thực hiện khi các khoản được TS đảm bảo đã `fully_paid` (cảnh báo nếu cố giải chấp sớm).
- BR-12: Mọi giá trị tiền mặc định VND `digits=(16,0)`; hỗ trợ đa tiền tệ ở field `currency_id`.

---

## 10. Tích hợp kế toán (Accounting Integration)

- v1: `re_loan` **không** bắt buộc Odoo Accounting. Ghi nhận số liệu vay + lịch
  + dư nợ độc lập.
- v2 (tùy chọn, nếu `account` được cài): sinh `account.move` cho giải ngân, lãi
  dồn tích, trả nợ; map journal/account theo cấu hình ngân hàng. Tương ứng
  `rf_account_ext` trong scope v4 — nhưng tối giản, chỉ cho loan.
- Đối chiếu với tiền gửi/tài khoản (BK đối chiếu KW vay) thuộc `_finance/` —
  ngoài phạm vi BRD này.

---

## 11. Tích hợp Realty Project (Bridge)

- Module `rp_loan_bridge` (đặt `_project/`) — **cài tùy chọn**, chỉ khi customer
  dùng cả vay + quản lý dự án xây dựng.
- Chức năng:
  - Phân bổ gốc/lãi KW tới `rp.structure` (hạng mục) + `rp.cost.category` (mã phí).
  - Báo cáo dòng tiền vay theo công trình.
  - Menu "Vay vốn" hiển thị trong app Realty Project.
- **Lưu ý phối hợp**: `addons/_project/` hiện do parallel chat (Realty Project)
  quản lý. Việc tạo `rp_loan_bridge` cần thống nhất với owner + parallel chat
  trước khi code (xem §16).

---

## 12. Báo cáo trong phạm vi (Reports — lõi)

| Mã | Báo cáo | Nguồn dữ liệu |
|---|---|---|
| R-1 | Dư nợ tổng hợp theo Ngân hàng | re.loan.note (group by bank) |
| R-2 | Dư nợ chi tiết theo HĐTD / Facility / KW | re.loan.note |
| R-3 | Lịch trả nợ sắp đến hạn (N ngày) | interest.line + repayment schedule |
| R-4 | Theo dõi nợ quá hạn (aging bucket) | re.loan.note + aging policy |
| R-5 | Tổng hợp tài sản thế chấp & giá trị đảm bảo | re.loan.collateral + pledge |
| R-6 | Dư nợ vay nội bộ theo công ty con | re.loan.onlending |

> Bộ 23 treasury reports đầy đủ của tài liệu nghiệp vụ nằm ở `_finance/rf_treasury_reports`.

---

## 13. Phụ thuộc & giả định (Dependencies & Assumptions)

- D-1: `re_party` đã có (extend res.partner). Cần bổ sung `is_bank`, MST,
  `parent_company_id` (cấu trúc tập đoàn) — *xác nhận trước khi code on-lending*.
- D-2: Master data ngân hàng: **v1 dùng `res.bank` + `res.partner` chuẩn Odoo**.
  Module `re_bank` đầy đủ (seed 20+ NH, mã NHNN, template per bank) để sau.
- D-3: `re.project` (re_base) dùng làm đích phân bổ generic — đã có.
- D-4: Multi-company: cần chốt mô hình (1 DB toàn tập đoàn vs mỗi cty 1 DB) vì
  ảnh hưởng on-lending + record rules — *câu hỏi mở §16*.
- D-5: Odoo 19, tuân `models.Constraint` (không `_sql_constraints`), date
  DD/MM/YYYY, VND `digits=(16,0)`.

---

## 14. Yêu cầu phi chức năng (Non-Functional)

- NFR-1: Đa công ty (multi-company) với record rules theo `company_id`.
- NFR-2: Tracking (`mail.thread`) trên HĐTD, KW, collateral; activity mixin để nhắc đáo hạn.
- NFR-3: Song ngữ Việt/Anh (`_()`), label nghiệp vụ tiếng Việt ưu tiên.
- NFR-4: Audit: không xoá cứng bản ghi có giao dịch; chỉ cancel/archive.
- NFR-5: Export Excel cho mọi báo cáo §12.

---

## 15. Đề xuất phân phase (Phasing)

| Phase | Scope | Ghi chú |
|---|---|---|
| **L0** | Foundation: extend `re_party` (is_bank, MST, parent_company_id); skeleton `re_loan` | Tiền đề on-lending + bank |
| **L1** | HĐTD + Facility + KW + Giải ngân + Trả nợ + lifecycle | MVP dùng được end-to-end |
| **L2** | Lãi vay (lịch lãi) + Phụ lục KW + báo cáo dư nợ/đến hạn/aging | Hoàn thiện theo dõi |
| **L3** | Tài sản thế chấp (định giá + multi-pledge + giải chấp) | |
| **L4** | Vay nội bộ (on-lending) + báo cáo dư nợ nội bộ | Cần `re_party.parent_company_id` |
| **L5** | Bridge `rp_loan_bridge` (phân bổ công trình) | Cần thống nhất với parallel chat |
| **L6** (tùy chọn) | Tích hợp kế toán `account.move` | Nếu Accounting được cài |

**Recommend bắt đầu L0 → L1** (MVP vay trực tiếp NH), test, rồi mở rộng.

---

## 16. Câu hỏi (Open Questions)

### 16.1 Đã chốt (owner 26/05/2026)

| # | Câu hỏi | Quyết định |
|---|---|---|
| OQ-1 | Multi-company | **1 DB** toàn tập đoàn (nhiều company records) |
| OQ-2 | Phương pháp tính lãi | **Dư nợ giảm dần** mặc định (để demo), nhưng **có option cho user chọn** phương pháp — thiết kế linh động |
| OQ-3 | Bank master | **Dùng `res.bank` chuẩn Odoo + custom thêm** (không cần `re_bank` đầy đủ ngay) |
| OQ-4 | Bridge Realty Project | **Có** làm `rp_loan_bridge` (cần phối hợp parallel chat trước khi sửa `_project/`) |
| OQ-5 | Phê duyệt nhiều cấp | **Để sau** — v1 tập trung logic + quy trình, chưa làm approval workflow |
| OQ-6 | Loại tiền | **Chỉ VND** (không cần đa tiền tệ / chênh lệch tỷ giá ở v1) |

### 16.2 Còn mở — phát sinh sau khi khảo sát source Viindoo tổng thầu đang có

- **OQ-7 — Build vs Reuse**: (A) viết mới `re_loan` Odoo 19; (B) port + extend
  Viindoo `xb_loan_management`; (C) viết mới nhưng tham khảo thuật toán Viindoo.
  *Recommend C.* Xem §19.
- **OQ-8 — Pháp lý**: owner có quyền fork/sửa/bán lại code Viindoo không? Module
  `l10n_vn_xb_loan_management` mang license **OPL-1** (Odoo Proprietary); core ghi
  LGPL-3 nhưng là bản rebrand Viindoo thương mại → nhãn đáng nghi. Nếu KHÔNG có
  quyền → loại B; C chỉ được tham khảo ý tưởng, không copy code.

---

## 17. Thuật ngữ (Glossary)

| Thuật ngữ | Tiếng Anh | Giải thích |
|---|---|---|
| HĐTD | Credit Contract / Master Credit Agreement | Hợp đồng tín dụng khung với ngân hàng |
| Hạn mức | Credit Facility | Giới hạn vay được cấp dưới HĐTD |
| Khế ước nhận nợ (KW) | Promissory Note / Drawdown | Từng lần rút vốn, ghi nhận nợ cụ thể |
| Giải ngân | Disbursement | NH chuyển tiền theo KW |
| Dư nợ gốc | Principal outstanding | Gốc còn phải trả |
| Thế chấp | Pledge / Collateral | Tài sản đảm bảo khoản vay |
| Giải chấp | Collateral release | Giải phóng TS khi tất toán |
| Vay nội bộ | Intercompany on-lending | Cty mẹ vay NH cho cty con vay lại |
| Phụ lục | Amendment | Văn bản sửa đổi HĐTD/KW |
| Quá hạn | Overdue | Trễ hạn trả gốc/lãi |
| Revolving | Revolving facility | Hạn mức tuần hoàn, hoàn lại khi trả |

---

## 19. Phụ lục — Đánh giá source Viindoo/Xboss tổng thầu đang có

tổng thầu đã mua module vay **Viindoo `to_loan_management`** (Odoo 17), rebrand thành
`xb_loan_management`; Xboss đang phát triển thêm. BSDInsight đã tự khảo sát source
(không chỉ dựa review bên thứ ba). Tóm tắt verify ngày 26/05/2026:

### 19.1 Cấu trúc (7 module)
- `xb_loan_management` (7,274 LOC) — engine lõi (rebrand Viindoo)
- `xb_loan_history` (254 LOC) — phần Xboss thêm (history khế ước)
- `l10n_vn_xb_loan_management` (271 LOC, **license OPL-1**) — l10n VN
- `xb_account`, `xb_account_base`, `xb_account_accountant`, `xb_base` — base layer

### 19.2 Engine Viindoo CÓ (đầy đủ hơn "thô sơ")
- `loan.borrowing.order` (đi vay) + `loan.lending.order` (cho vay)
- Disbursement (`loan.borrow.disbursement` / `loan.lend.disbursement`) đóng vai
  "khế ước": `promissory_note_no`, `expected_refund_date`, state, account, journal
- Interest line + `loan.floating.rate` + `loan.interest.rate.type` (floating)
- Refund (trả nợ) line + payment matching / **đối chiếu** với `account.move`
- Tích hợp sâu `account.move`, `account.payment`, analytic

### 19.3 Engine Viindoo THIẾU (verify grep = 0) — đúng các gap BRD bù đắp
- Tài sản thế chấp (collateral) — 0
- Liên kết dự án/công trình — 0 (chỉ analytic_distribution)
- Tầng credit line / facility / hạn mức trên Order — 0
- Phụ lục/amendment là entity riêng — 0
- Intercompany back-to-back (nối KW con ↔ KW mẹ) — 0

### 19.4 Bug Xboss (`xb_loan_history`) — verify đúng
- `states={'draft':[...]}` cú pháp Odoo ≤15 (bỏ ở 17), >10 chỗ → field luôn readonly
- Typo `disbusement_number` (thiếu 'r') ở 4 file
- Ref sai model `loan.borrowing.disbursement` (thật là `loan.borrow.disbursement`)
- `action_draft` xoá sạch `history_ids` → phá mục đích bảng history

### 19.5 Kết luận
Engine Viindoo giải quyết tốt tầng Order→KW→Lãi→Trả nợ→Đối chiếu kế toán, nhưng
thiếu đúng 5 thứ đặc thù tổng thầu (facility, collateral, project link, amendment,
intercompany) — là phần BRD này thiết kế. Phần Xboss thêm chất lượng kém, không
production-grade. Khuyến nghị **Option C** (viết mới `re_loan` Odoo 19 generic,
tham khảo thuật toán lãi/đối chiếu của Viindoo), chờ owner xác nhận OQ-7 + OQ-8.

---

*Hết BRD v1.0 (draft). Owner review → chốt OQ-7/OQ-8 → chuyển sang SDD (thiết kế
kỹ thuật) + bắt đầu code L0.*
