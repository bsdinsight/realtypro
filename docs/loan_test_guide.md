# Hướng dẫn Test & Demo — Quản lý Vay + Realty Project bridge

**Phiên bản module**:
- `re_loan` 19.0.1.7.0 (L0–L4)
- `rp_contract` 19.0.1.0.0 (HĐ nhà thầu)
- `rp_loan_bridge` 19.0.1.0.0 (L5)
- `re_loan_account` 19.0.1.0.0 (L6)
- `re_party` 19.0.0.3.0 (extend)

**Ngày**: 26/05/2026
**Đối tượng**: Team BSDInsight (dev / tester / BA) — làm việc, test, học, và chuẩn bị demo cho CC1
**Tài liệu liên quan**: `docs/loan_brd.md` (nghiệp vụ), `docs/loan_sdd.md` (thiết kế kỹ thuật)

> Module viết MỚI 100% (clean-room), IP của BSDInsight. Không dùng code Viindoo.

---

## 1. Tổng quan các module

5 module phối hợp tạo chuỗi vay vốn end-to-end:

```
re_loan                  ← Quản lý vay lõi (HĐTD/Facility/KW/Lãi/Thế chấp)
   ↑
re_loan_account          ← L6: post account.move (cấu hình mapping COA)
   ↑
rp_loan_bridge           ← L5: phân bổ vay theo công trình
   ↓
rp_contract              ← HĐ nhà thầu (kết nối từ rp_estimate)
   ↓
rp_estimate + rp_cost_base + rp_contractor + re_base
```

Cấu trúc nghiệp vụ:

```
Hợp đồng tín dụng (HĐTD) → Hạn mức (Facility) → Khế ước nhận nợ (KW)
                                                   ├── Giải ngân ─────► account.move
                                                   ├── Lịch lãi  ─────► account.move (capitalize)
                                                   ├── Trả nợ  ───────► account.move
                                                   ├── Phụ lục KW
                                                   ├── Tài sản thế chấp (multi-pledge)
                                                   ├── Vay nội bộ (on-lending)
                                                   └── Phân bổ công trình ─┐
                                                                            ↓
       Project → Khu vực → Hạng mục → Gói thầu → HĐ nhà thầu (rp.contract)
                                                   ├── BOQ
                                                   ├── Lịch thanh toán
                                                   ├── Phụ lục HĐ
                                                   └── Bảo lãnh (TH/Tạm ứng/Bảo hành)
```

19 model. Apps: **Quản lý Vay** + **Realty Project**.

| Phase | Nội dung | Module | Trạng thái |
|---|---|---|---|
| L0 | Nền tảng + extend re_party (is_bank, công ty mẹ-con) + loại TS thế chấp | re_loan | ✅ |
| L1a | HĐTD + Hạn mức | re_loan | ✅ |
| L1b | Khế ước nhận nợ + Giải ngân + Trả nợ | re_loan | ✅ |
| L2a | Lịch lãi tự động (dư nợ giảm dần / cố định) | re_loan | ✅ |
| L2b | Phụ lục KW (6 loại) | re_loan | ✅ |
| L2c | Báo cáo + cron quá hạn / nhắc đáo hạn | re_loan | ✅ |
| L3 | Tài sản thế chấp (định giá + multi-pledge + giải chấp) | re_loan | ✅ |
| L4 | Vay nội bộ (on-lending) | re_loan | ✅ |
| RP-1 | HĐ nhà thầu (rp.contract) + BOQ + lịch TT + phụ lục + bảo lãnh | rp_contract | ✅ |
| L5 | Bridge phân bổ công trình | rp_loan_bridge | ✅ |
| L6 | Tích hợp kế toán `account.move` | re_loan_account | ✅ |

---

## 2. Môi trường & truy cập

| Thông tin | Giá trị |
|---|---|
| URL | http://localhost:8169/odoo?db=dev |
| Login | admin@dev.localhost / admin (hoặc admin/admin) |
| DB | dev |
| Container web | rp-dev-web (port 8169 → 8069) |
| Container DB | rp-dev-db (postgres) |
| Đường dẫn code | `~/projects/realtypro_dev/addons/{_common,_project}/` |

Apps hiển thị ở launcher: **Quản lý Vay** + **Realty Project**. Cần user
thuộc nhóm *Realty Loan / User* hoặc *Manager* (admin đã có sẵn).

### Lệnh thường dùng (dev)

```bash
cd ~/projects/realtypro_dev

# Upgrade module sau khi sửa code
docker compose stop web
docker compose run --rm web odoo -d dev -u re_loan --stop-after-init --no-http
docker compose up -d web

# Chạy test tự động — cả module loan
docker compose run --rm web odoo -d dev -u re_loan \
    --test-enable --test-tags re_loan --stop-after-init --no-http

# rp.contract (22 tests)
docker compose run --rm web odoo -d dev -u rp_contract \
    --test-enable --test-tags rp_contract --stop-after-init --no-http

# rp_loan_bridge (10 tests)
docker compose run --rm web odoo -d dev -u rp_loan_bridge \
    --test-enable --test-tags rp_loan_bridge --stop-after-init --no-http

# re_loan_account (5 tests)
docker compose run --rm web odoo -d dev -u re_loan_account \
    --test-enable --test-tags re_loan_account --stop-after-init --no-http

# Tổng: 123 tests (77 + 22 + 10 + 5 + 9 từ re_party)
```

---

## 3. Dữ liệu demo (đã seed sẵn trong DB `dev`)

> Đây là số liệu test chuẩn để team đối chiếu. Toàn bộ cũng nằm trong
> `re_loan/demo/*.xml` (nạp tự động khi cài DB mới có demo).

### 3.1 Ngân hàng (res.partner, is_bank=True)
BIDV, Vietcombank, VietinBank, Agribank, Techcombank, SHB (6 NH).

### 3.2 Hợp đồng tín dụng (HĐTD)

| Số HĐTD | Ngân hàng | Trạng thái | Tổng hạn mức |
|---|---|---|---|
| HĐTD-2026/001 | BIDV | Hiệu lực | 500 tỷ |
| HĐTD-2026/002 | Vietcombank | Hiệu lực | 300 tỷ |
| HĐTD-2026/003 | VietinBank | Nháp | 1,000 tỷ |

### 3.3 Hạn mức (Facility)

| Thuộc HĐTD | Tên | Loại | Hạn mức | Đã dùng | Lãi suất | PP lãi | Day-count |
|---|---|---|---|---|---|---|---|
| 001 | Vốn lưu động | revolving | 300 tỷ | **150 tỷ** | 8.5% | giảm dần | act_360 |
| 001 | Trung hạn | term | 200 tỷ | **150 tỷ** | 10% | giảm dần | act_360 |
| 002 | Vốn lưu động | revolving | 300 tỷ | 0 | 8% | giảm dần | act_360 |
| 003 | Dài hạn dự án | term | 700 tỷ | 0 | 9.5% | giảm dần | act_360 |
| 003 | Bảo lãnh | guarantee_line | 300 tỷ | 0 | 2% | cố định | act_360 |

### 3.4 Khế ước nhận nợ (KW)

| Số KW | Loại | Số tiền | Lãi | Kỳ hạn | Dư nợ gốc | Tổng lãi dự kiến | Trạng thái |
|---|---|---|---|---|---|---|---|
| KW-2026/0001 | vay NH | 200 tỷ | 8.5% | 12 th | **150 tỷ** | ~17.24 tỷ | Trả một phần |
| KW-2026/0002 | vay NH | 150 tỷ | 10% | 24 th | 150 tỷ | ~30.42 tỷ | Hiệu lực |
| KW-OL-2026/01 | cho vay lại | 80 tỷ | 9.5% | 12 th | 80 tỷ | ~7.71 tỷ | Hiệu lực |

- KW-2026/0001: giải ngân 200 tỷ, trả gốc 50 tỷ → dư nợ 150 tỷ (revolving hoàn 50 tỷ hạn mức).
- KW-2026/0002: giải ngân 150 tỷ, chưa trả (term — hạn mức không hoàn).
- KW-OL-2026/01: cho **CC1 - Công ty con Miền Nam** vay lại 80 tỷ từ KW-2026/0001 @ 9.5% (> lãi nguồn 8.5%).

### 3.5 Tài sản thế chấp

| Tài sản | Loại | Giá trị hiện hành | Đang đảm bảo | Trạng thái |
|---|---|---|---|---|
| Đất dự án Khu A | Bất động sản | 800 tỷ | 300 tỷ (cho KW-2026/0001) | Đang thế chấp |

### 3.6 Cấu trúc tập đoàn (vay nội bộ)
- Tổng Công ty CC1 (mẹ) → CC1 - Công ty con Miền Nam (con, `parent_company_id`).

### 3.7 Hợp đồng nhà thầu (rp.contract — Realty Project)

| Số HĐ | Gói thầu | Nhà thầu | Giá trị HĐ (sau VAT) | Đã trả | Tiến độ | Trạng thái |
|---|---|---|---|---|---|---|
| HD-2026/CXCQ-01 | Gói cây xanh cảnh quan - Đảo mặt trời | Công ty xây dựng CC1 | 54 tỷ (50 + 8% VAT) | 16.2 tỷ (tạm ứng 30%) | 30% | Đang thực hiện |

- 3 mốc thanh toán: Tạm ứng 30% (đã trả), Đợt 1 — 50% KL (40%), Nghiệm thu hoàn thành (25%).
- Bảo lãnh thực hiện HĐ: BL-TH-001 / BIDV / 2.7 tỷ / hết hạn 2027-12-31.

### 3.8 Phân bổ vay theo công trình (rp.loan.allocation — L5)

KW-2026/0001 (BIDV revolving 200 tỷ) phân bổ:

| # | Base | Đích | Method | Giá trị | Mục đích |
|---|---|---|---|---|---|
| 1 | Lãi | Vinhomes / cost cat **CPTC** (Financing Cost) | 100% | ~17.24 tỷ | Capitalize toàn bộ lãi vay |
| 2 | Gốc | Vinhomes / Hạng mục Tầng hầm Toà A / HĐ HD-2026/CXCQ-01 | 50 tỷ amount | 50 tỷ | Tài trợ HĐ cây xanh cảnh quan |

---

## 4. Kịch bản test (UAT) — theo tính năng

> Ký hiệu: **[M]** = Manager, **[U]** = User. Mọi giá trị tiền là VND.

### TC-1: Tạo HĐTD + Hạn mức (L1a)
1. Quản lý Vay → Hợp đồng tín dụng → **New**.
2. Nhập Số HĐTD, chọn Ngân hàng (chỉ NH có cờ Bank/Lender hiện ra), Tổng hạn mức.
3. Tab **Hạn mức** → thêm 2 dòng facility, tổng ≤ tổng HĐTD.
4. **Kích hoạt** → trạng thái Hiệu lực.
- ✅ Kỳ vọng: tổng hạn mức facility ≤ tổng HĐTD (vượt → báo lỗi). "Hạn mức HĐTD còn lại" tính đúng.

### TC-2: Tạo Khế ước + Giải ngân + Trả nợ (L1b)
1. Khế ước nhận nợ → **New**: chọn Hạn mức, nhập số tiền (≤ hạn mức còn lại), kỳ hạn → Ngày đáo hạn tự tính.
2. **Kích hoạt** → Hiệu lực, lịch lãi tự sinh.
3. Tab **Giải ngân** → thêm dòng (≤ số tiền KW).
4. Tab **Trả nợ** → thêm dòng trả gốc + lãi.
- ✅ Kỳ vọng: Dư nợ gốc = giải ngân − trả gốc. Trả hết → Đã tất toán. Revolving: facility hoàn hạn mức; Term: không hoàn.
- ❌ Test chặn: giải ngân > số tiền KW; trả gốc > đã giải ngân; KW > hạn mức còn lại.

### TC-3: Lịch lãi (L2a)
1. Mở 1 KW Hiệu lực → tab **Lịch lãi**: kiểm tra số kỳ = kỳ hạn.
2. Đổi phương pháp lãi (dư nợ giảm dần ↔ cố định) → **Tạo lại lịch lãi** → so sánh.
3. Bật **Sửa tay** 1 dòng → nhập tiền lãi thủ công.
- ✅ Kỳ vọng: dư nợ giảm dần → base giảm theo kỳ (nếu trả gốc đều); cố định → base = gốc ban đầu mọi kỳ. act_360 cho lãi cao hơn act_365.

### TC-4: Phụ lục KW (L2b)
1. Mở KW → tab **Phụ lục** → New → chọn loại (vd Đổi lãi suất) → nhập lãi mới → Save → **Áp dụng**.
2. Kiểm tra KW đã đổi lãi + tab Lịch lãi tự cập nhật + audit value cũ→mới.
- ✅ Kỳ vọng: không áp dụng 2 lần, không xoá phụ lục đã áp dụng.

### TC-5: Báo cáo + Quá hạn (L2c)
1. **Báo cáo → Dư nợ vay**: pivot theo Ngân hàng × Trạng thái.
2. **Báo cáo → Khế ước đến hạn**: lọc đáo hạn ≤ 90 ngày.
3. **Báo cáo → Nợ quá hạn (Aging)**: pivot theo nhóm tuổi nợ.
4. Cron: tạo 1 KW có ngày đáo hạn quá khứ + giải ngân → chạy cron (Settings → Technical → Scheduled Actions → "Loan: cập nhật quá hạn") → KW chuyển Quá hạn.
- ✅ Kỳ vọng: aging bucket đúng theo số ngày quá hạn; activity nhắc đáo hạn được tạo (không trùng).

### TC-6: Tài sản thế chấp (L3)
1. **Tài sản thế chấp → New**: tên, loại, pháp lý.
2. Tab **Định giá** → thêm 2 lần định giá khác ngày → "Giá trị hiện hành" = lần mới nhất.
3. Tab **Thế chấp** → thêm pledge gắn KW hoặc HĐTD, nhập giá trị đảm bảo → TS chuyển "Đang thế chấp".
4. Nút **Giải chấp** → TS về "Sẵn sàng".
- ✅ Kỳ vọng: multi-pledge (1 TS nhiều khoản); total_secured = tổng đảm bảo active; pledge phải gắn HĐTD hoặc KW.

### TC-7: Vay nội bộ (L4)
1. **Vay nội bộ → New**: chọn KW nguồn (vay NH), Bên vay (công ty con), số tiền, lãi suất.
2. **Kích hoạt** → nếu lãi cho vay lại < lãi nguồn → cảnh báo trên chatter.
3. Mở KW nguồn → tab **Cho vay lại** → thấy khoản con + "Đã cho vay lại".
- ✅ Kỳ vọng: tổng cho vay lại ≤ số tiền KW nguồn; on-lending có giải ngân/lịch lãi/trả nợ như KW thường.

### TC-8: HĐ nhà thầu (rp.contract)
1. **Realty Project → Project Master → Hợp đồng nhà thầu → New**.
2. Chọn Gói thầu + Nhà thầu, nhập giá trị HĐ trước thuế, VAT 8%, tạm ứng 30%, retention 5%.
   Verify computed: vat_amount, contract_value_total, amount_advance, amount_retention.
3. Tab **Lịch thanh toán** → thêm 3 mốc (Tạm ứng 30%, Đợt 1 = 40%, Hoàn thành = 25%) — Σ ≤ 100%.
4. (Optional) Tab **Khối lượng (BOQ)** → thêm lines, Σ phải = giá trị HĐ trước thuế (check khi ký).
5. Tab **Bảo lãnh** → nhập số BL, NH, số tiền, hết hạn cho 3 nhóm (TH/Tạm ứng/Bảo hành).
6. **Ký HĐ** → state `signed`. **Khởi công** → `executing`.
7. Trên milestone, click nút **Đã trả** → tiến độ % cập nhật.
8. Tab **Phụ lục** → tạo Gia hạn / Đổi giá trị / … → **Áp dụng** → audit value cũ→mới.
- ✅ Kỳ vọng: lifecycle đúng; Σ % milestone ≤ 100; Σ line ≈ giá trị HĐ (sai số ≤ 1) khi ký; mở Gói thầu thấy smart button số HĐ + tổng giá trị HĐ đã ký.

### TC-9: Phân bổ vay theo công trình (L5 bridge)
1. Mở 1 KW (vd KW-2026/0001) → tab **Phân bổ công trình** → thêm dòng:
   - Project = Vinhomes, Cost category = CPTC (Financing Cost)
   - Base = Lãi, Method = %, Percent = 100
   - → Σ phân bổ lãi ≈ 17.24 tỷ
2. Thêm dòng thứ 2: Project = Vinhomes, Structure = "Tầng hầm Toà A", HĐ = HD-2026/CXCQ-01
   - Base = Gốc, Method = amount, Amount = 50,000,000,000
3. Mở **Realty Project → Hạng mục → Tầng hầm Toà A → tab Vay phân bổ**: thấy 50 tỷ.
4. Mở **HD-2026/CXCQ-01 → tab Vay tài trợ**: thấy 50 tỷ gốc tài trợ HĐ.
5. **Báo cáo → Phân bổ vay theo công trình** (truy cập từ cả Realty Project lẫn Quản lý Vay):
   pivot theo Dự án × Hạng mục × Base.
- ✅ Kỳ vọng: rollup `loan_allocated_amount` trên hạng mục + HĐ đúng; constraint chặn nếu structure/cost cat/contract khác project.

### TC-10: Post bút toán kế toán (L6)
**Cấu hình trước** (Settings → Realty Loan):
- TK Vay = 3411, TK Bank = 1121, TK Lãi phải trả = 33531
- TK CP lãi = 635, TK XDCB = 241, Sổ Nhật ký = "Loan Journal"

**Test giải ngân**:
1. Mở 1 KW → tab Giải ngân → thêm 1 dòng → click nút **Post** (icon bookmark).
2. Verify: `account.move` được tạo + posted, Nợ TK 1121 / Có TK 3411, balanced.

**Test trả nợ**:
3. Tab Trả nợ → thêm 1 dòng (gốc + lãi) → click **Post**.
4. Verify: move 3 line: Nợ 3411 (gốc) + Nợ 33531 (lãi) / Có 1121 (tổng).

**Test lãi capitalize**:
5. Tạo allocation trên KW: base=interest, cost_category set, % = 60% (TC-9).
6. Mở 1 dòng lịch lãi → click **Ghi nhận**.
7. Verify: capitalized_amount ≈ 60% × interest_amount → vào TK 241; expense_amount = 40% → vào TK 635.

- ✅ Kỳ vọng: move balanced, posted; không cho post 2 lần; nếu bridge không cài hoặc chưa có allocation → toàn bộ lãi vào TK 635.
- ❌ Chặn: chưa cấu hình TK trong Settings → UserError yêu cầu cấu hình.

---

## 5. Test tự động (123 tests tổng cộng)

Chạy theo từng module (xem lệnh ở Section 2):

| Module | Số test | Phủ |
|---|---|---|
| **re_loan** | **77** | (chi tiết bên dưới) |
| └─ test_credit_contract.py | 12 | HĐTD + Facility |
| └─ test_loan_note.py | 15 | KW + giải ngân + trả nợ + hạn mức |
| └─ test_interest_schedule.py | 10 | Lịch lãi + thuật toán |
| └─ test_amendment.py | 10 | Phụ lục |
| └─ test_cron_aging.py | 10 | Cron + aging + nhắc đáo hạn |
| └─ test_collateral.py | 10 | TS thế chấp |
| └─ test_onlending.py | 10 | Vay nội bộ |
| **re_party** | 9 | Quan hệ + địa chỉ thường trú (legacy CRM track) |
| **rp_contract** | 22 | HĐ nhà thầu + lifecycle + milestone + phụ lục |
| **rp_loan_bridge** | 10 | Phân bổ vay theo công trình + rollup |
| **re_loan_account** | 5 | Post account.move + capitalize |
| **TOTAL** | **123** | 0 failed |

---

## 6. Ghi chú học tập (cho team)

### Nghiệp vụ vay VN
- **Khế ước nhận nợ (KW)** là entity lõi, không phải HĐTD. 1 HĐTD → nhiều lần rút
  vốn, mỗi lần 1 KW có dư nợ/lãi/đáo hạn riêng. Khác "loan trả góp" của ERP ngoại.
- **Revolving vs Term**: revolving hoàn hạn mức khi trả nợ (đo theo dư nợ thực);
  term cam kết, không hoàn (đo theo số tiền KW).
- **Dư nợ giảm dần** (declining): lãi tính trên dư nợ thực tế — phổ biến NH VN.
  **act_360**: NH VN thường tính lãi theo 360 ngày/năm.
- **Vay nội bộ (on-lending)**: tập đoàn mẹ vay NH cho con vay lại, lãi ≥ lãi gốc.

### Nghiệp vụ HĐ nhà thầu
- Chuỗi VN: Project → Khu vực → Hạng mục → Gói thầu → **HĐ nhà thầu**.
  Gói thầu là phạm vi đấu thầu; HĐ nhà thầu là kết quả ký sau đấu thầu.
- 1 gói thầu có thể có nhiều HĐ (vd subcontract). 1 HĐ thuộc 1 gói.
- Bảo lãnh (TH HĐ / Tạm ứng / Bảo hành) là 3 chứng từ khác nhau từ NH —
  hiện lưu text fields; sẽ FK sang module `rf_bank_guarantee` (scope CC1) khi ship.
- Tạm ứng 10-30% là chuẩn VN; retention 5% giữ lại bảo hành 12-24 tháng.

### Kế toán vay VN (VAS TT 200)
- **5 nhóm TK** liên quan: 3411/3412 (vay), 1121 (tiền gửi NH), 33531 (lãi
  phải trả), 635 (CP lãi không capitalize), 241 (XDCB capitalize).
- **§54 Capitalization**: chi phí đi vay phát sinh trong giai đoạn XDCB được
  vốn hoá vào giá thành tài sản dở dang (TK 241). Sau khi đưa vào sử dụng,
  lãi vay đi vào CP lãi (TK 635).
- Module L6 cho phép cấu hình **tỷ lệ capitalize** thông qua `rp.loan.allocation`
  (bridge L5): nếu KW có allocation tới cost_category → phần đó capitalize.

### Kỹ thuật Odoo (điểm hay gặp)
- `@api.constrains` chỉ chạy khi field trong danh sách nằm trong vals lúc
  create → với ràng buộc "bắt buộc có 1 trong nhiều field", phải gọi check tường
  minh trong `create()` override (xem pledge, facility).
- Field computed **không store** → không filter/group trong search view (Odoo
  validate lúc load → ParseError). Dùng field stored (vd `aging_bucket`).
- Trong eval của XML data, `datetime` = class `datetime.datetime`, `timedelta`
  có sẵn → dùng `datetime.now()`, không `datetime.datetime.now()`.
- Search view: filter group-by đặt thẳng trong `<search>`, không bọc `<group expand>`.
- `res.groups` Odoo 19 dùng `user_ids` (không `users`), không `category_id`.

---

## 7. Kịch bản DEMO cho CC1 (story end-to-end ~15 phút)

> Mục tiêu: cho CC1 thấy module giải quyết đúng nghiệp vụ vay tổng thầu mà
> Viindoo/Xboss còn thiếu (4 tầng + thế chấp + công trình + vay nội bộ).

**Bước 1 — Khung hạn mức tín dụng (2')**
Mở **HĐTD-2026/001 (BIDV, 500 tỷ)** → cho thấy 2 hạn mức (revolving 300 + term
200), "đã dùng" tự cập nhật. Nhấn mạnh: 1 HĐTD nhiều hạn mức — Viindoo không có
tầng này.

**Bước 2 — Rút vốn theo khế ước (3')**
Mở **KW-2026/0001 (200 tỷ)**: giải ngân 200 tỷ, đã trả gốc 50 tỷ → dư nợ 150 tỷ.
Quay lại facility revolving → đã hoàn 50 tỷ (còn dùng 150 tỷ). Cho thấy KW là
entity lõi có dư nợ/lãi riêng.

**Bước 3 — Lịch lãi tự động (2')**
Tab **Lịch lãi** của KW: 12 kỳ, tổng lãi dự kiến ~17.24 tỷ. Đổi phương pháp →
Tạo lại lịch → cho thấy tính linh động (dư nợ giảm dần / cố định / act_360-365).

**Bước 4 — Phụ lục (2')**
Tạo phụ lục **Gia hạn** hoặc **Đổi lãi suất** → Áp dụng → lịch lãi cập nhật,
có audit. Đây là thứ Xboss nhồi thành text — ta làm thành entity có vòng đời.

**Bước 5 — Tài sản thế chấp (2')**
Mở **Đất dự án Khu A (800 tỷ)** → định giá nhiều lần, thế chấp 300 tỷ cho
KW-2026/0001, multi-pledge. Viindoo **không có** collateral.

**Bước 6 — Vay nội bộ (2')**
Mở **KW-OL-2026/01**: CC1 cho công ty con vay lại 80 tỷ @ 9.5% từ khoản vay
BIDV 8.5% → biên lãi 1%. Đúng nghiệp vụ tập đoàn CC1.

**Bước 7 — HĐ nhà thầu + Bridge phân bổ công trình (3')**
Mở **HD-2026/CXCQ-01** (HĐ nhà thầu cho CC1, 54 tỷ): cho thấy lifecycle, milestones,
bảo lãnh. Quay lại KW-2026/0001 → tab **Phân bổ công trình** → thấy 2 dòng:
- Lãi 100% → cost cat **CPTC** (Financing Cost) của Vinhomes (= 17.24 tỷ capitalize)
- Gốc 50 tỷ → hạng mục **Tầng hầm Toà A** / HĐ cây xanh CC1 (cashflow tracking)

Mở **Hạng mục Tầng hầm Toà A → tab Vay phân bổ** thấy 50 tỷ. Mở HĐ → tab Vay
tài trợ thấy 50 tỷ. **Chuỗi end-to-end Project → Khu vực → Hạng mục → Gói thầu
→ HĐ nhà thầu giờ đã hoàn chỉnh** — đây là khác biệt cốt lõi với Viindoo
(không có liên kết công trình).

**Bước 8 — Kế toán tự động (2')**
Mở 1 dòng giải ngân → click **Post** → `account.move` được tạo (Nợ 1121 / Có 3411).
Mở 1 dòng lịch lãi → click **Ghi nhận** → móng nối với allocation 60% → 60% lãi
vào TK 241 (XDCB), 40% vào TK 635 (CP lãi). Đây là **§54 VAS TT 200** —
capitalize lãi vay vào giá thành công trình, hoàn toàn tự động.

**Báo cáo → Dư nợ vay** (pivot theo NH), **Nợ quá hạn (Aging)**, **Phân bổ vay
theo công trình** (pivot Project × Hạng mục × Base). Cron tự đánh dấu quá hạn
+ nhắc đáo hạn.

**Chốt**: nhấn mạnh 7 thứ Viindoo/Xboss thiếu mà module này có:
1. Tầng hạn mức tín dụng (Facility) trên HĐTD
2. Phụ lục là entity có vòng đời (không phải text field)
3. Tài sản thế chấp đa pledge + định giá
4. Vay nội bộ (intercompany on-lending)
5. **Phân bổ vay theo Hạng mục / Gói thầu / HĐ nhà thầu (L5)**
6. **Tự động capitalize lãi vay theo TT 200 §54 (L6)**
7. HĐ nhà thầu đầy đủ (BOQ, milestones, phụ lục, bảo lãnh)

---

## 8. Giới hạn hiện tại / chưa làm

- **Phê duyệt nhiều cấp**: chưa làm (OQ-5 — để sau khi nghiệp vụ ổn).
- **Đa tiền tệ**: chỉ VND (OQ-6). Field `currency_id` có sẵn để mở rộng.
- **Biểu mẫu in NH per-bank** (UNC, giấy nhận nợ): thuộc domain `_finance/`
  trong scope CC1 — chưa ship (`rf_bank_forms`).
- **`rf_bank_guarantee`** (CC1 scope): module bảo lãnh đầy đủ chưa ship; HĐ nhà
  thầu lưu BL ở text fields, sẽ FK khi module này có.
- **HĐ nhà thầu — multi-bidder/award workflow**: chưa làm (Phase 5 sau của
  Realty Project). v1 đã đủ dùng để demo end-to-end.
- Lịch lãi là **dự kiến** (forecast theo số tiền KW), chưa khớp giải ngân thực
  tế từng phần — sẽ tinh chỉnh nếu CC1 yêu cầu chính xác từng đợt giải ngân.
- **Capitalization tỷ lệ**: hiện đọc allocation `interest`. Future: cho phép cấu
  hình bằng cost-category-type=`capitalize` flag để control sạch hơn.

---

*Hết hướng dẫn. Thắc mắc về nghiệp vụ xem `loan_brd.md`; chi tiết kỹ thuật xem
`loan_sdd.md`.*
