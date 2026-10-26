# Khuôn bảng điều khiển EAMOne — hợp đồng giữa các màn

Hai bảng điều khiển đang làm song song:

| màn | trả lời câu | ai làm |
|---|---|---|
| **Ca trực sáng nay** | *hôm nay tôi phải làm gì trước* | phiên fork |
| **Toàn danh mục nhà máy** | *nhà máy nào đang kéo cả đội xuống* | phiên chính |

Hai câu khác nhau nên hai màn, nhưng **một phong cách**. Tài liệu này là
thứ giữ cho chúng không trôi thành hai sản phẩm.

## 1. Bắt đầu từ đâu

- `depends` thêm `eam_dashboard`. Không khai lại SCSS, không chép màu.
- Thẻ ngoài cùng của màn: `<div class="eam-dash">`. Mọi lớp dưới đây
  chỉ có tác dụng bên trong nó.
- Dựng theo khuôn **client action OWL**, giống `eam_map` và `eam_tree`.
  Không dùng app *Dashboards* của Odoo (`spreadsheet_dashboard`).

## 2. Bảng màu — chỉ dùng biến, không gõ mã màu

```
--navy #0f2c3f   --teal #0e8c99   --bg  #f1f4f5   --card #ffffff
--ink  #0f2c3f   --muted #5c7480  --line #dde6e9
--good #2e7d5b   --warn #c99a2e   --bad #c0453b   --unknown #8fa3ad
```

`--unknown` là màu của **chưa đo được**, và nó cố ý KHÔNG phải màu xấu.
Chưa đo được không phải tin xấu, nó là tin *"không biết"*. Tô đỏ thì
người đọc hiểu nhầm là hỏng; để trắng thì họ đọc nhầm là 0.

## 3. Danh sách lớp

**Đầu trang** — `.eam-dash-header` · `.eam-dash-eyebrow` ·
`.eam-dash-title` · `.eam-dash-tools` · `.eam-dash-today`

**Trạng thái** — `.eam-dash-loading` · `.eam-dash-empty`

**Thẻ số** — `.eam-kpis` (4 cột, có `.eam-kpis-3`, `.eam-kpis-2`) chứa
`.eam-card` ▸ `.eam-card-label` / `.eam-card-value` (`.u` cho đơn vị) /
`.eam-card-sub`. Thêm `.is-good` `.is-warn` `.is-bad` `.is-unknown`.
`.eam-hero` cho thẻ nổi nền chuyển sắc navy→teal.

**Khối** — `.eam-row` (2fr 1fr) hoặc `.eam-row-even` · `.eam-panel` ▸
`.eam-panel-head` (có `h3`) / `.eam-panel-note` · `.eam-chart`

**Thanh** — `.eam-bars` ▸ `.eam-bar-top` / `.eam-bar-name` /
`.eam-bar-val` / `.eam-bar-track` ▸ `.eam-bar-fill` / `.eam-bar-pct`

**Bảng** — `.eam-table`; ô số dùng `td.num`, ô giữa `td.c`, ô mờ
`td.muted`, **ô chưa đo được `td.unknown`**. Dòng tô nền: `tr.is-bad`,
`tr.is-warn`.

**Khác** — `.eam-chip` (+ `.is-good/.is-warn/.is-bad/.is-unknown`) ·
`.eam-divider` (dải chia mục) · `.eam-todo` cho dòng việc phải làm
(`.eam-todo-count` / `.eam-todo-text` / `.eam-todo-sub`, thêm
`.is-zero` khi đếm bằng 0).

## 4. Ba luật không được phá

**① Chưa đo được thì in dấu gạch, KHÔNG in số 0.** Dùng
`td.unknown` hoặc `.eam-card.is-unknown` với nội dung `—`. Đây là
xương sống của cả bộ EAMOne: một con số 0 giả làm người đọc kết luận
sai mà vẫn thấy báo cáo đầy đủ.

**② Tỷ lệ phải kèm mẫu số.** Khả dụng 97% trên hai ngày có số không
giống 97% trên cả tháng. Để mẫu số ở `.eam-card-sub` hoặc `.eam-bar-val`.

**③ Không sửa biến trong `eam_dash.scss`.** Cần nét riêng thì thêm lớp
con dưới `.eam-dash`. Sửa biến gốc là đổi luôn màn của người kia, và
người ta chỉ phát hiện khi mở ra thấy màu lạ.

## 5. Bẫy bố cục đã trả giá rồi

Khung cha `.o_action_manager` có `overflow:hidden`, nên dashboard
**phải tự cuộn**: `height:100%` + `overflow-y:auto`. Đừng dùng
`min-height` — nó nở hết chiều cao nội dung rồi **chặn luôn cuộn
chuột**, và lỗi đó trông y như trang bị đơ. Luật này đã nằm sẵn trong
`.eam-dash`, chỉ cần đừng ghi đè.

## 6. Nguồn số liệu, để hai màn không nói khác nhau

| con số | lấy từ |
|---|---|
| khả dụng, sản lượng, hệ số công suất theo tổ máy/ngày | `eam.unit.day` |
| PR / PA điện mặt trời | `eam.solar.kpi` |
| sản lượng & doanh thu theo kỳ | `eam.energy.period`, `rp.energy.period` |
| tổn thất đã quy ra tiền | `eam.loss.day`, `eam.loss.day.line` |
| cảnh báo đang mở | `eam.alarm` (`state in new/ack/wo`) |
| lệnh quá hạn | `eam.work.order` |
| PM tới hạn & quá hạn | `eam.pm.schedule` |
| cảnh báo kho | `eam.stock` |
| KPI hợp đồng O&M | `eam.om.period` |

**Bậc kỳ**: `eam.energy.period` lưu cùng một lượng điện thành bốn bậc
(ngày/tuần/tháng/năm). Luôn lọc `loai_ky`, nếu không là cộng gấp bốn.
