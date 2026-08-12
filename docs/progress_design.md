# Module Quản lý Tiến độ — Design Document

> **Trạng thái:** Draft for discussion — chưa code, chưa lock.
> **Mục đích:** Thống nhất scope + kiến trúc trước khi triển khai.
> **Đối tượng đọc:** BSDInsight tech + tổng thầu PM/CFO/KTT.

---

## 1. Tóm tắt quyết định (đã chốt với anh)

| Quyết định | Lựa chọn |
|---|---|
| Đơn vị tiến độ chính | **BBN KLCV theo HĐ nhà thầu** (xương sống) |
| Link với re_loan | **Có** — BBN duyệt → unlock tranche giải ngân |
| Gantt chart | **Có ngay từ đầu** |
| Scope | **Full** — BBN + Gantt + EVM + 5 báo cáo |
| Thời gian dự kiến | **~6 tuần** chia 4 phase |

---

## 2. Module mới: `rp_progress`

### 2.1 Dependencies

```
rp_progress
  ├── re_base              (re.project, re.subzone)
  ├── rp_cost_base         (rp.cost.category, rp.structure)
  ├── rp_estimate          (BOQ — dự toán)
  ├── rp_contract          (HĐ nhà thầu, payment milestone)
  └── (optional) re_loan + rp_loan_bridge — bật khi cần link loan
```

### 2.2 Vị trí trong suite Realty Project

- Foundation độc lập với `re_loan` — KH chỉ Project (không Loan) cũng dùng được
- Bridge `rp_progress_loan` (nếu cần tách) hoặc tích hợp soft-dependency

---

## 3. Data Model

### 3.1 Entity LÕI: `rp.progress.acceptance` (BBN KLCV)

Mỗi BBN là 1 chứng từ pháp lý xác nhận khối lượng đã thi công trong 1 kỳ
(tháng) của 1 HĐ nhà thầu.

```python
class RpProgressAcceptance(models.Model):
    _name = 'rp.progress.acceptance'
    _description = 'Biên bản nghiệm thu khối lượng (BBN KLCV)'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = Char  # Số BBN (vd "BBN-2026/01-HĐ45")
    contract_id = M2O('rp.contract', required)
    project_id = M2O(related='contract_id.project_id', store=True)
    period_year = Integer  # 2026
    period_month = Integer  # 1..12
    date_proposed = Date  # Ngày nhà thầu đề xuất
    date_approved = Date  # Ngày CĐT duyệt
    representative_contractor = Char  # Người ký bên thầu
    representative_owner = Char       # Người ký bên CĐT
    note = Text

    line_ids = O2M('rp.progress.acceptance.line')

    # Computed
    total_value_period = Monetary    # Σ giá trị nghiệm thu kỳ này
    total_value_to_date = Monetary   # Σ lũy kế đến hết kỳ này
    progress_percent = Float         # % hoàn thành HĐ (lũy kế / HĐ value)

    state = Selection([
        ('draft', 'Nháp'),
        ('proposed', 'Đã đề xuất'),
        ('approved', 'CĐT duyệt'),
        ('cancelled', 'Huỷ'),
    ])

    # Link đến payment + loan disbursement
    payment_milestone_id = M2O('rp.contract.payment.milestone',
                                readonly=True)
    invoice_id = M2O('account.move', readonly=True)
    unlocked_disbursement_ids = O2M('re.loan.note.disbursement')
```

### 3.2 Entity: `rp.progress.acceptance.line`

Mỗi dòng tương ứng 1 đầu việc trong BOQ (cost.category × structure).

```python
class RpProgressAcceptanceLine(models.Model):
    _name = 'rp.progress.acceptance.line'

    acceptance_id = M2O('rp.progress.acceptance', ondelete='cascade')
    cost_category_id = M2O('rp.cost.category', required)
    structure_id = M2O('rp.structure')

    # Tham chiếu BOQ — pre-fill từ rp.structure.estimate.line
    estimate_line_id = M2O('rp.structure.estimate.line')

    description = Char     # Tên công việc
    uom = Char             # Đơn vị tính (m², m³, kg, ...)
    unit_price = Monetary  # Đơn giá BOQ

    quantity_estimated = Float    # KL dự toán (snapshot từ BOQ)
    quantity_to_date_prev = Float # KL lũy kế kỳ trước (auto từ BBN trước)
    quantity_this_period = Float  # KL kỳ này (USER NHẬP)
    quantity_to_date = Float      # = prev + this (computed)

    # Computed
    amount_this_period = quantity_this_period × unit_price
    amount_to_date = quantity_to_date × unit_price
    progress_percent = quantity_to_date / quantity_estimated × 100
```

### 3.3 Mở rộng `rp.structure` (compute rolled-up)

```python
# Thêm vào rp.structure
progress_percent = Float(compute, store)
  # = Σ(acceptance_line.amount_to_date trên structure này)
  #   / Σ(estimate_line.amount trên structure này)
progress_value = Monetary  # Σ giá trị đã nghiệm thu
status = Selection(compute):
  not_started / in_progress / completed / delayed / paused

# Tiến độ kế hoạch
date_planned_start = Date
date_planned_end   = Date
date_actual_start  = Date(compute)  # Ngày BBN đầu tiên có KL trên structure này
date_actual_end    = Date(compute)  # Khi progress_percent >= 100

is_delayed = Boolean(compute)
  # True nếu today > date_planned_end và progress_percent < 100
days_delayed = Integer(compute)
```

### 3.4 Mở rộng `rp.contract`

```python
# Thêm vào rp.contract
acceptance_ids = O2M('rp.progress.acceptance')
acceptance_count = Integer(compute)
acceptance_value_to_date = Monetary(compute, store)
progress_percent = Float(compute, store)
  # = acceptance_value_to_date / contract_value
paid_percent = Float(compute)  # đã thanh toán / contract_value
schedule_variance_days = Integer(compute)  # ngày sớm/trễ vs kế hoạch
```

### 3.5 Mở rộng `re.project`

```python
weighted_progress_percent = Float(compute, store)
  # = Σ(structure.progress_percent × structure.weight)
  # weight = structure.estimate_value / Σ estimate_value
delayed_structure_count = Integer(compute)
project_status = Selection(compute):
  on_track / at_risk / behind / critical
```

### 3.6 Entity (Gantt): `rp.progress.task` (optional layer)

Cho Gantt chart visualization. KHÔNG bắt buộc — derived từ structure.

```python
class RpProgressTask(models.Model):
    _name = 'rp.progress.task'

    structure_id = M2O('rp.structure')
    name = related('structure_id.name')
    date_start = related('structure_id.date_planned_start')
    date_end   = related('structure_id.date_planned_end')
    progress = related('structure_id.progress_percent')
    dependency_ids = M2M('rp.progress.task', 'predecessor_ids')
```

---

## 4. Workflow

### 4.1 BBN KLCV state machine

```
[Nháp]
   │ (NT nhập KL kỳ + đề xuất ký)
   ▼
[Đã đề xuất]
   │ (CĐT review + ký)
   ├──→ [Huỷ]
   ▼
[CĐT duyệt] ─────────────────────────┐
   │                                  │
   ├─ Auto: tạo payment milestone     │
   ├─ Auto: tạo dự thảo invoice NT    │
   └─ Auto: unlock disbursement       │
       tranche tiếp theo (nếu link    │
       với re_loan)                   │
                                       ▼
                              (Lifecycle hoàn tất)
```

### 4.2 Loan integration flow

```
HĐTD ─ Facility ─ KW ─┬─ Disbursement #1 (auto unlock)
                       │
                       ├─ Disbursement #2 ──── locked
                       │                    └─ require BBN #1 approved
                       │
                       ├─ Disbursement #3 ──── locked
                       │                    └─ require BBN #2 approved
                       │
                       └─ ...

BBN approved → set disbursement[N].is_unlocked = True
            → notify cán bộ tín dụng "có thể giải ngân tiếp"
```

`re.loan.note.disbursement`: thêm field
- `required_acceptance_id` M2O → BBN required to unlock
- `is_unlocked` Boolean (compute: True nếu BBN approved)

---

## 5. Earned Value Management (EVM)

Tính theo VAS-style (đơn giản — chỉ dùng amount, không cần resource hourly).

| Metric | Công thức | Ý nghĩa VN |
|---|---|---|
| **PV** (Planned Value) | Σ estimate × planned_% | Giá trị KH theo lịch |
| **EV** (Earned Value) | Σ acceptance_value_to_date | Giá trị đã nghiệm thu |
| **AC** (Actual Cost) | Σ invoice_paid_for_contract | Thực chi |
| **SPI** = EV / PV | >1 nhanh, <1 chậm | Hiệu suất tiến độ |
| **CPI** = EV / AC | >1 tiết kiệm, <1 vượt | Hiệu suất chi phí |
| **EAC** = BAC / CPI | Total cost forecast | Dự báo tổng chi |

Compute trên `re.project` field:
- `evm_pv`, `evm_ev`, `evm_ac`, `evm_spi`, `evm_cpi`, `evm_eac`

Snapshot hàng tháng vào `rp.progress.evm.snapshot` để xem trend.

---

## 6. Views & UX

### 6.1 Kanban tiến độ trên `rp.structure`

```
Chưa khởi công | Đang thi công | Hoàn thành | Chậm tiến độ
─────────────  | ─────────────  | ─────────  | ────────────
[Móng]         | [Thân #1] 67%  | [Vây cọc]  | [MEP] -15d
[Hoàn thiện]   | [Thân #2] 42%  | [Hầm B1]   | [PCCC] -7d
```

### 6.2 Form BBN KLCV

```
┌─ BBN-2026/01-HĐ45 ───────────── [Đã đề xuất] ───┐
│ [Đề xuất] [Duyệt] [Huỷ]                          │
│                                                   │
│ HĐ nhà thầu: HĐ45 — XD móng Block A             │
│ Kỳ: 2026/01    Đề xuất: 25/01    Duyệt: -       │
│                                                   │
│ ─── Khối lượng ─────────────────────────────────  │
│ CV │ Hạng mục │ ĐVT │ KL DT │ KL kỳ │ Lũy kế │ % │
│ M1 │ Móng A   │ m³  │ 1.000 │ 200   │ 700    │70%│
│ M2 │ Móng B   │ m³  │  800  │ 100   │ 400    │50%│
│ ─────────────────────────────────────────────────  │
│ Σ giá trị nghiệm thu kỳ: 1.5 tỷ                   │
│ Σ lũy kế: 5.2 tỷ / 8 tỷ (65%)                    │
│                                                   │
│ Người ký NT: Nguyễn Văn A                        │
│ Người ký CĐT: Trần Thị B                         │
└───────────────────────────────────────────────────┘
```

### 6.3 Gantt chart trên `re.project`

```
Module: OCA web_gantt (Odoo 19 compatible fork) hoặc custom OWL.
Source: rp.structure.date_planned_start/end + progress_percent.

[Móng]           ████████░░ 80%  [Jan─Apr]
[Thân #1]        ███░░░░░░░ 30%  [Apr─Sep]
[Thân #2]        ░░░░░░░░░░  0%  [Jun─Nov]    ← critical path
[Hoàn thiện]     ░░░░░░░░░░  0%  [Oct─Dec]
[MEP]            ██░░░░░░░░ 15%  [Aug─Dec]
                 │              │
                 today          deadline
```

### 6.4 Dashboard `re.project` form

- Progress bar tổng dự án (weighted)
- 3 KPI card: Tiến độ kế hoạch / Tiến độ thực tế / SPI
- Bảng top 5 hạng mục đang chậm nhất
- Smart button: BBN KLCV count, total value

---

## 7. Báo cáo (5 mẫu)

| # | Báo cáo | Format | Mục đích |
|---|---|---|---|
| 1 | **Báo cáo tiến độ tháng** | PDF (Qweb) | VAS-style — gửi CĐT, BLĐ. Header: tháng/dự án. Body: kế hoạch / thực tế / chênh lệch / lý do delay. |
| 2 | **So sánh KH vs Thực tế** | Pivot view | Hạng mục × tháng, measure = progress_percent. Trend qua các kỳ. |
| 3 | **Bảng kê BBN KLCV** | List + export Excel | Liệt kê BBN đã ký theo HĐ × kỳ. Phục vụ kế toán đối chiếu hồ sơ. |
| 4 | **Cảnh báo delay** | List + cron daily | Hạng mục delay > N ngày → tạo activity cho PM. |
| 5 | **EVM Dashboard** | Pivot + Graph | PV / EV / AC / SPI / CPI theo tháng — phục vụ CFO. |

---

## 8. Integration: Loan ↔ Progress

### 8.1 Unlock disbursement bằng BBN

Cấu hình ở Facility hoặc per Disbursement:
- `disbursement_unlock_mode` = "auto" (rút bất kỳ) / "by_acceptance" (cần BBN)
- Khi `by_acceptance`: thêm field `required_acceptance_id` cho từng tranche

Flow:
1. Cán bộ tín dụng tạo KW + plan các tranche giải ngân, gắn `required_acceptance_id` cho tranche 2, 3, …
2. Tranche 1 (mobilization): không cần BBN → giải ngân ngay
3. Tranche 2 lock cho đến khi BBN tháng 1 approved
4. BBN tháng 1 approved → server action set `is_unlocked = True` trên tranche 2
5. Cán bộ tín dụng giải ngân tranche 2
6. … lặp lại

### 8.2 Auto-create invoice nhà thầu khi BBN duyệt

- BBN approved → tạo dự thảo `account.move` (vendor bill):
  - partner = contract.contractor_id
  - lines: 1 dòng tổng = total_value_period
  - reference = BBN number
  - context = link tới BBN

- Khi KTT post invoice → auto-create payment milestone trên `rp.contract`.

### 8.3 Capitalize lãi vay theo tiến độ (re_loan_account)

Đã có sẵn cơ chế trong `re_loan_account`. Tích hợp:
- Lãi vay capitalize vào TK 241 theo % allocation
- % allocation có thể compute từ tiến độ thi công (EV / total estimate)
  → tự động tỉ lệ với thực tế, không cần KTT nhập tay

---

## 9. Timeline phased

### Phase P1 — BBN core (2 tuần)
- [ ] Module skeleton `rp_progress` (manifest, security, ACL)
- [ ] Entity `rp.progress.acceptance` + lines
- [ ] Workflow state machine (draft → proposed → approved)
- [ ] Compute rolled-up: structure / contract / project
- [ ] List + Form + Kanban views
- [ ] Báo cáo (3): Bảng kê BBN KLCV
- [ ] Tests

### Phase P2 — Loan integration (1 tuần)
- [ ] Extend `re.loan.note.disbursement`: required_acceptance_id, is_unlocked
- [ ] Server action unlock khi BBN approved
- [ ] Smart button "BBN ràng buộc" trên disbursement
- [ ] Capitalize tự động theo tiến độ thi công

### Phase P3 — Gantt + Reports (1.5 tuần)
- [ ] Tích hợp OCA `web_gantt` (fork Odoo 19) hoặc OWL custom
- [ ] Gantt view trên project / structure
- [ ] Critical path basic (longest chain)
- [ ] Báo cáo (1): PDF tiến độ tháng
- [ ] Báo cáo (2): Pivot KH vs thực tế

### Phase P4 — EVM + Polish (1.5 tuần)
- [ ] Compute PV / EV / AC / SPI / CPI trên project
- [ ] Entity snapshot hàng tháng `rp.progress.evm.snapshot`
- [ ] Báo cáo (5): EVM dashboard (pivot + graph)
- [ ] Báo cáo (4): Cron cảnh báo delay
- [ ] Dashboard tổng trên project form
- [ ] Documentation + training material

**Tổng:** 6 tuần ± buffer

---

## 10. Câu hỏi mở — cần tổng thầu xác nhận trước khi P1

1. **Đơn vị BBN:** theo tháng (chuẩn VN) hay tuần/quý? → em đoán **tháng**
2. **Workflow ký:** chỉ 2 bên (NT + CĐT) hay có thêm Tư vấn giám sát (TVGS)? → ảnh hưởng state machine
3. **Số BBN:** tự động hay nhập tay? Format: `BBN-{YYYY}/{MM}-HĐ{xx}` OK?
4. **BOQ chuẩn:** tổng thầu đã có template BOQ hay cần BSDInsight tạo?
5. **Đơn vị tính (UOM):** danh mục đóng (m², m³, kg, tấn, bộ, cái) hay mở?
6. **Mức điều chỉnh BOQ:** có cho phép sửa quantity_estimated giữa kỳ (vd phát sinh)? Workflow phụ lục HĐ?
7. **Multi-currency:** BBN dùng currency của HĐ. OK chứ?
8. **Tích hợp MS Project / Primavera:** có cần import/export `.mpp`/`.xer` không?

---

## 11. Rủi ro & Giảm thiểu

| Rủi ro | Khả năng | Giảm thiểu |
|---|---|---|
| OCA web_gantt chưa hỗ trợ Odoo 19 | Cao | Backup plan: viết OWL custom (1 tuần thêm) |
| BOQ data quá rời rạc, khó link cost.category với structure | Trung | Migration script + UI wizard import từ Excel |
| KTT phản đối "thêm bước BBN" | Thấp | Demo: BBN tự động drive invoice → ÍT thao tác hơn |
| EVM phức tạp cho KTT VN không quen | Trung | Báo cáo VAS-friendly + tooltip giải thích |
| NH không chấp nhận BBN điện tử | Thấp | Vẫn xuất PDF BBN có chữ ký scan → NH nhận |

---

## 12. Câu hỏi tiếp theo

Trước khi em bắt tay vào code Phase P1:

1. Anh có muốn em viết **BRD chi tiết** cho tổng thầu review không, hay sang code luôn?
2. Anh có muốn em tạo **demo mockup** (PDF / Figma) cho tổng thầu xem trước UI/UX không?
3. Tên module: `rp_progress` OK chứ, hay đặt khác?

---

_BSDInsight • 05/2026 • Module `rp_progress` v0.1 design draft_
