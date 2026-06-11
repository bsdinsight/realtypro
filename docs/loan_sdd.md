# SDD — Quản lý Vay (Loan Management)

**Module**: `re_loan` (Realty Pro — `_common/` foundation) + bridge `rp_loan_bridge`
**Phiên bản**: v1.0 (draft)
**Ngày**: 26/05/2026
**Tác giả**: BSDInsight (Claude Code)
**Tài liệu nguồn**: `docs/loan_brd.md` v1.0
**Trạng thái**: Draft — chờ owner review

> **Tuyên bố clean-room**: Thiết kế này viết MỚI hoàn toàn, là IP của BSDInsight
> để thương mại hoá. Module Viindoo `to_loan_management`/`xb_loan_management` chỉ
> được **đọc tham khảo ý tưởng nghiệp vụ** (OQ-7=C). **KHÔNG copy code, không
> copy tên model/field, không tái sử dụng XML** của Viindoo (OQ-8: không có quyền
> fork/bán lại). Công thức tính lãi dùng ở đây là toán tài chính phổ thông
> (declining balance / flat), không phải IP của ai.

---

## 1. Quyết định nền (từ BRD §16.1)

| # | Quyết định |
|---|---|
| OQ-1 | **1 DB** đa công ty (multi-company records, record rules theo `company_id`) |
| OQ-2 | Lãi **dư nợ giảm dần** mặc định, **pluggable** cho phép user chọn method khác |
| OQ-3 | Bank master = **`res.bank` chuẩn** + custom nhẹ (chưa làm `re_bank`) |
| OQ-4 | **Có** bridge `rp_loan_bridge` (phối hợp parallel chat trước khi sửa `_project/`) |
| OQ-5 | **Chưa** approval workflow — v1 tập trung logic + quy trình |
| OQ-6 | **Chỉ VND** (field `currency_id` vẫn có để mở rộng sau, default VND) |
| OQ-7 | Build = **C** (viết mới, tham khảo Viindoo) |
| OQ-8 | **Không** có quyền dùng code Viindoo → clean-room |

---

## 2. Kiến trúc & cấu trúc module

```
addons/_common/re_loan/
├── __manifest__.py        depends: ['base','mail','re_party','re_base']
├── models/
│   ├── __init__.py
│   ├── re_loan_credit_contract.py
│   ├── re_loan_facility.py
│   ├── re_loan_note.py                 ← entity LÕI
│   ├── re_loan_note_disbursement.py
│   ├── re_loan_note_interest_line.py
│   ├── re_loan_note_repayment.py
│   ├── re_loan_note_amendment.py
│   ├── re_loan_note_project_allocation.py
│   ├── re_loan_collateral.py
│   ├── re_loan_collateral_type.py
│   ├── re_loan_collateral_valuation.py
│   ├── re_loan_collateral_pledge.py
│   ├── re_loan_collateral_release.py
│   └── res_partner.py                  (nếu cần bổ sung, phần chính ở re_party)
├── security/
│   ├── re_loan_groups.xml              group_loan_user, group_loan_manager
│   ├── re_loan_rules.xml               record rules company_id
│   └── ir.model.access.csv
├── data/
│   ├── re_loan_collateral_type_data.xml   seed loại TS
│   └── ir_cron_data.xml                cron overdue + nhắc đáo hạn
├── views/
│   ├── menu_root.xml
│   ├── re_loan_credit_contract_views.xml
│   ├── re_loan_facility_views.xml
│   ├── re_loan_note_views.xml
│   ├── re_loan_collateral_views.xml
│   └── re_loan_report_views.xml        pivot/list báo cáo lõi
└── report/                             (L6) QWeb generic UNC/giấy nhận nợ

addons/_project/rp_loan_bridge/         (L5 — cần phối hợp parallel chat)
└── inherit rp.structure (+ loan_note_ids), phân bổ tới hạng mục/mã phí
```

**Naming**: model `re.loan.*`, prefix module `re_*` (foundation `_common/`).
**Versioning**: bắt đầu `19.0.1.0.0`.

---

## 3. Mô hình dữ liệu chi tiết

> Ký hiệu: ✱ = required. Tiền dùng `Monetary` + `currency_id` (default VND
> `digits=(16,0)`). Model user-facing kế thừa `mail.thread`, `mail.activity.mixin`.

### 3.1 `re.loan.credit.contract` — Hợp đồng tín dụng (HĐTD)

| Field | Type | Ghi chú |
|---|---|---|
| name ✱ | Char | Số HĐTD, `copy=False`, tracking |
| partner_id ✱ | M2O res.partner | Bên cho vay (NH); domain ưu tiên `is_bank=True` |
| bank_id | M2O res.bank | Chi nhánh / mã NH (OQ-3) |
| company_id ✱ | M2O res.company | Bên vay (cty mình); default env.company |
| sign_date | Date | Ngày ký |
| date_start | Date | Hiệu lực |
| date_end | Date | Hết hạn |
| amount_total ✱ | Monetary | Tổng hạn mức HĐTD |
| currency_id ✱ | M2O res.currency | Default VND |
| representative | Char | Người đại diện ký |
| state | Selection | draft/active/expired/closed/cancelled |
| facility_ids | O2M facility | |
| amount_facility_total | Monetary compute | Σ amount_limit facilities |
| note | Text | |

**Constraint**: `amount_facility_total ≤ amount_total` (BR-1).
**State machine**: draft →(action_activate)→ active →(expire/close/cancel).

### 3.2 `re.loan.facility` — Hạn mức

| Field | Type | Ghi chú |
|---|---|---|
| name ✱ | Char | |
| credit_contract_id ✱ | M2O | ondelete=cascade |
| facility_type ✱ | Selection | revolving / term / overdraft / guarantee_line / lc_line |
| amount_limit ✱ | Monetary | |
| date_start, date_end | Date | |
| interest_rate_default | Float | %/năm |
| interest_method | Selection | declining / flat (default declining) — OQ-2 |
| day_count | Selection | act_365 / act_360 / 30_360 (default act_365) |
| note_ids | O2M re.loan.note | |
| amount_used | Monetary compute store | Σ `principal_outstanding` của note active/partial |
| amount_available | Monetary compute | amount_limit − amount_used |
| currency_id, company_id | related từ contract | |

**Constraint**: tạo/active note → `note.amount ≤ amount_available` (BR-2).
**Revolving**: note `fully_paid` → hoàn `amount_used` (BR-6).

### 3.3 `re.loan.note` — Khế ước nhận nợ (KW) — LÕI

| Field | Type | Ghi chú |
|---|---|---|
| name ✱ | Char | Số KW, copy=False, tracking |
| loan_type ✱ | Selection | `external` (vay NH) / `onlending` (cho vay lại nội bộ) — default external |
| facility_id ✱ | M2O facility | (external); với onlending có thể null |
| source_note_id | M2O re.loan.note | Chỉ onlending: KW external nguồn (BR-7) |
| counterparty_company_id | M2O res.company | Chỉ onlending: cty con vay lại |
| partner_id | related/M2O | external: NH (từ contract); onlending: cty con |
| company_id ✱ | M2O res.company | Bên ghi sổ |
| date_note ✱ | Date | Ngày nhận nợ |
| amount ✱ | Monetary | Số tiền KW |
| interest_rate ✱ | Float | %/năm |
| interest_method | Selection | declining/flat, default từ facility (OQ-2) |
| day_count | Selection | default từ facility |
| tenor_months | Integer | Kỳ hạn (tháng) |
| date_maturity ✱ | Date | Ngày đáo hạn (= date_note + tenor) |
| repayment_plan | Selection | bullet (cuối kỳ) / equal_principal (gốc đều) / custom |
| purpose | Text | Mục đích sử dụng vốn |
| state | Selection | draft/active/partial_paid/fully_paid/overdue/restructured/cancelled |
| disbursement_ids | O2M | |
| interest_line_ids | O2M | |
| repayment_ids | O2M | |
| amendment_ids | O2M | |
| allocation_ids | O2M project allocation | |
| pledge_ids | O2M collateral pledge | (note-level) |
| onlending_ids | O2M re.loan.note | inverse source_note_id (các KW con) |
| amount_disbursed | Monetary compute | Σ disbursement |
| amount_repaid_principal | Monetary compute | Σ repayment.amount_principal |
| amount_repaid_interest | Monetary compute | Σ repayment.amount_interest |
| principal_outstanding | Monetary compute store | amount_disbursed − amount_repaid_principal |
| interest_accrued | Monetary compute | Σ interest_line.interest_amount (accrued) |
| is_overdue | Boolean compute store | set bởi cron (BR-5) |
| days_overdue | Integer compute | |

**Quyết định thiết kế (deviation từ BRD §8)**: hợp nhất "vay nội bộ" vào
`re.loan.note` qua `loan_type` thay vì model `re.loan.onlending` riêng. Lý do:
on-lending có cùng cấu trúc con (giải ngân/lãi/trả nợ/phụ lục) → DRY, 1 bộ view,
1 bộ logic. KW onlending phân biệt bằng `loan_type='onlending'` + `source_note_id`
+ `counterparty_company_id`. *Cần owner xác nhận chọn hợp nhất này.*

**Constraints**:
- BR-3: Σ disbursement ≤ amount
- BR-4: Σ repayment.principal ≤ amount_disbursed
- BR-7: Σ amount của onlending notes ≤ source_note.amount
- BR-8: onlending interest_rate ≥ source rate → cảnh báo (UserError soft? → warning trên form, không chặn)

**State machine**:
```
draft ──action_activate──► active
active/partial_paid ──(repayment)──► partial_paid ──(repay hết)──► fully_paid
active/partial_paid ──(cron, quá hạn & dư nợ>0)──► overdue
active/partial_paid ──action_restructure (amendment)──► restructured
draft/active/partial_paid ──action_cancel──► cancelled
```

### 3.4 `re.loan.note.disbursement` — Giải ngân
| Field | Type |
|---|---|
| note_id ✱ | M2O cascade |
| date ✱ | Date |
| amount ✱ | Monetary |
| journal_id | M2O account.journal (L6) |
| bank_account | Char / M2O res.partner.bank |
| reference | Char (số chứng từ) |

### 3.5 `re.loan.note.interest.line` — Lịch lãi
| Field | Type | Ghi chú |
|---|---|---|
| note_id ✱ | M2O cascade | |
| period_no | Integer | Kỳ |
| date_from, date_to ✱ | Date | |
| days | Integer compute | (date_to − date_from) |
| principal_base ✱ | Monetary | Dư nợ đầu kỳ |
| interest_rate | Float | |
| interest_amount | Monetary compute | (xem §4) |
| is_overridden | Boolean | Cho phép sửa tay |
| interest_amount_manual | Monetary | Khi override |
| state | Selection | planned / accrued / paid |

### 3.6 `re.loan.note.repayment` — Trả nợ
| Field | Type |
|---|---|
| note_id ✱ | M2O cascade |
| date ✱ | Date |
| amount_principal | Monetary |
| amount_interest | Monetary |
| amount_total | Monetary compute |
| reference | Char |

### 3.7 `re.loan.note.amendment` — Phụ lục KW
| Field | Type | Ghi chú |
|---|---|---|
| name ✱ | Char | Số phụ lục |
| note_id ✱ | M2O cascade | |
| amendment_type ✱ | Selection | extension/amount/rate/purpose/schedule/collateral |
| date_effective ✱ | Date | |
| value_old | Char | |
| value_new | Char | |
| note | Text | |

Áp dụng: `action_apply()` ghi giá trị mới vào KW (vd extension → cập nhật
`date_maturity`; rate → `interest_rate`), KW có thể chuyển `restructured`.

### 3.8 `re.loan.note.project.allocation` — Phân bổ công trình
| Field | Type | Ghi chú |
|---|---|---|
| note_id ✱ | M2O cascade | |
| project_id ✱ | M2O re.project | (re_base — generic) |
| base | Selection | principal / interest / both |
| method | Selection | percent / amount |
| percent | Float | nếu method=percent |
| amount | Monetary | nếu method=amount |

**Constraint** BR-9: Σ percent = 100 (nếu percent) hoặc Σ amount = note.amount.
Bridge `rp_loan_bridge` mở rộng tới `rp.structure` + `rp.cost.category`.

### 3.9 Collateral (Tài sản thế chấp)

**`re.loan.collateral.type`** (seed): BĐS, phương tiện, hàng tồn kho, quyền tài
sản (quyền đòi nợ CĐT), cổ phần, bảo lãnh bên thứ ba.

**`re.loan.collateral`**
| Field | Type | Ghi chú |
|---|---|---|
| name ✱ | Char | |
| type_id ✱ | M2O type | |
| owner_company_id | M2O res.company | Cty thành viên sở hữu |
| owner_partner_id | M2O res.partner | (nếu của bên thứ ba) |
| legal_info | Text | Pháp lý (sổ đỏ, đăng ký…) |
| valuation_ids | O2M | |
| value_current | Monetary compute | Định giá mới nhất |
| pledge_ids | O2M | |
| total_secured | Monetary compute | Σ secured_amount pledge active |
| state | Selection | available / pledged / released |

**`re.loan.collateral.valuation`**: collateral_id, date, amount, method
(market/cost/income/appraisal), appraiser (Char).

**`re.loan.collateral.pledge`** (multi-pledge)
| Field | Type | Ghi chú |
|---|---|---|
| collateral_id ✱ | M2O | |
| credit_contract_id | M2O | đảm bảo cấp HĐTD |
| note_id | M2O | hoặc đảm bảo cấp KW |
| date_pledge ✱ | Date | |
| secured_amount | Monetary | Giá trị đảm bảo cho khoản này |
| state | Selection | active / released |
| release_id | M2O release | |

1 collateral → N pledge (BR-3 collateral). Constraint: ít nhất 1 trong
(credit_contract_id, note_id) phải có.

**`re.loan.collateral.release`** (giải chấp): collateral_id, date_release,
reason, pledge_ids. BR-11: cảnh báo nếu khoản được đảm bảo chưa fully_paid.

---

## 4. Thuật toán tính lãi (pluggable — OQ-2)

Hook `_compute_interest_amount(line)` dispatch theo `note.interest_method`:

```
day_factor(day_count):
    act_365 → days/365
    act_360 → days/360
    30_360  → 30/360 mỗi kỳ tháng

declining (dư nợ giảm dần) — MẶC ĐỊNH:
    interest = principal_base × rate × day_factor
    với principal_base = dư nợ gốc thực tế đầu kỳ
    (giảm dần khi trả gốc)

flat (lãi cố định trên gốc ban đầu):
    interest = note.amount × rate × day_factor
    (base không đổi qua các kỳ)
```

- `_generate_interest_schedule()` sinh `interest_line_ids` khi KW `active`, dựa
  `tenor_months`, `repayment_plan`, `date_note`.
- Mở rộng tương lai: thêm method `annuity` (trả góp đều) chỉ cần thêm nhánh
  dispatch — không phá schema. Đây là điểm "linh động" owner yêu cầu.
- Override tay: `is_overridden=True` → dùng `interest_amount_manual` (khi NH tính
  lệch do quy ước ngày).

---

## 5. Cron & cảnh báo

- `ir_cron` **Loan: mark overdue** — chạy hằng ngày: KW `active/partial_paid` mà
  `date_maturity < today` và `principal_outstanding > 0` → `is_overdue=True`,
  state `overdue` (BR-5).
- `ir_cron` **Loan: maturity reminder** — tạo `mail.activity` cho người phụ trách
  khi KW/HĐTD/định giá TS sắp đáo hạn (N ngày, cấu hình `res.config.settings`).

---

## 6. Báo cáo lõi (L2)

| Mã | Báo cáo | Kỹ thuật |
|---|---|---|
| R-1 | Dư nợ theo Ngân hàng | pivot trên re.loan.note (group partner_id) |
| R-2 | Dư nợ theo HĐTD/Facility/KW | list + group |
| R-3 | Lịch trả nợ đến hạn (N ngày) | search view interest_line + repayment schedule |
| R-4 | Nợ quá hạn (aging) | TransientModel `re.loan.aging.report` + bucket cấu hình |
| R-5 | TS thế chấp & giá trị đảm bảo | list collateral + pledge |
| R-6 | Dư nợ vay nội bộ theo cty con | pivot note (loan_type=onlending) |

Aging bucket (cấu hình): trong hạn, 1-30, 31-60, 61-90, 91-180, 181-365, >365.
Export Excel: dùng `xlsxwriter` qua report action (như chuẩn Odoo).

---

## 7. Security (OQ-5: chưa approval, chỉ phân quyền cơ bản)

- Groups: `group_loan_user` (CRUD nghiệp vụ), `group_loan_manager` (cấu hình +
  xoá + cancel).
- ACL `ir.model.access.csv` cho toàn bộ model.
- Record rule multi-company: mọi model có `company_id`, rule
  `['|',('company_id','=',False),('company_id','in',company_ids)]`.

---

## 8. Menu & UI

```
Quản lý Vay (root: menu_re_loan_root)
├── Hợp đồng tín dụng        (re.loan.credit.contract)
├── Khế ước nhận nợ          (re.loan.note)  ← màn hình chính
├── Vay nội bộ               (re.loan.note filtered loan_type=onlending)
├── Tài sản thế chấp         (re.loan.collateral)
├── Báo cáo
│   ├── Dư nợ theo NH/HĐTD/KW
│   ├── Lịch trả nợ đến hạn
│   ├── Nợ quá hạn (aging)
│   └── TS thế chấp
└── Cấu hình
    ├── Loại tài sản thế chấp
    └── Settings (reminder days, aging buckets)
```

Form KW: header nút (Confirm/Restructure/Cancel) + statusbar; notebook tab
Giải ngân / Lịch lãi / Trả nợ / Phụ lục / Phân bổ công trình / Tài sản thế chấp;
smart button dư nợ.

Bridge `rp_loan_bridge`: chèn menu "Vay vốn" vào app Realty Project + tab phân bổ
trên `rp.structure`.

---

## 9. Tích hợp kế toán (L6 — OQ "dùng Odoo + custom")

- v1 (L0–L5): ghi nhận số liệu vay độc lập, **không** bắt buộc Accounting.
- L6 (tùy chọn, khi `account` cài): sinh `account.move`:
  - Giải ngân: Nợ TK tiền gửi / Có TK vay (theo facility_type → account map)
  - Lãi dồn tích: Nợ CP lãi vay / Có lãi phải trả
  - Trả nợ: Nợ vay + lãi phải trả / Có tiền gửi
  - Cấu hình journal/account theo NH (res.bank) + facility_type.

---

## 10. Mapping phase (build order)

| Phase | Module/Model | Trạng thái SDD |
|---|---|---|
| **L0** | `re_party` extend (is_bank, vn_tax_code đã có, parent_company_id) + `re_loan` skeleton (manifest, groups, ACL, root menu, collateral type seed) | **Build now** |
| **L1** | credit.contract + facility + note + disbursement + repayment + state machine (chưa lịch lãi tự động — nhập tay) | **Build now** |
| **L2** | interest.line (declining+flat) + amendment + báo cáo R1-R4 + cron overdue/reminder | Design done |
| **L3** | collateral + type + valuation + pledge + release (R5) | Design done |
| **L4** | onlending (loan_type=onlending) + R6 | Design done |
| **L5** | bridge `rp_loan_bridge` (phối hợp parallel chat) | Design sketch |
| **L6** | account.move integration | Design sketch |

**Recommend bắt đầu: L0 → L1** (MVP vay trực tiếp NH end-to-end), demo, rồi L2.

---

## 11. Câu hỏi kỹ thuật cần owner xác nhận trước khi code L0

- **TQ-1**: Hợp nhất on-lending vào `re.loan.note` qua `loan_type` (DRY) — đồng ý
  thay vì model `re.loan.onlending` riêng như BRD §8?
- **TQ-2**: `re_party` cần thêm `parent_company_id` (cấu trúc tập đoàn cty mẹ-con)
  — tôi thêm vào `re_party` ở L0. Xác nhận?
- **TQ-3**: Menu "Quản lý Vay" đứng riêng (app root mới) hay nằm trong app Realty
  Project? (Bridge L5 sẽ chèn vào Project; nhưng generic nên có root riêng.)
  Recommend: **root riêng** + bridge chèn thêm.
- **TQ-4**: `day_count` mặc định `act_365` hay `act_360`? (NH VN hay dùng 360.)
  Recommend default **act_360** cho đúng thực tế VN, vẫn cho chọn.
- **TQ-5**: Số KW / số HĐTD — tự sinh sequence (`ir.sequence`) hay nhập tay theo
  số NH cấp? Recommend: **nhập tay** (số do NH cấp), có thể optional sequence nội bộ.

---

*Hết SDD v1.0 (draft). Owner xác nhận TQ-1→TQ-5 → bắt đầu code L0.*
