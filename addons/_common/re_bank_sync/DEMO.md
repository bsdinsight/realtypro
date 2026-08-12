# Kịch bản demo — Đối soát ngân hàng qua SePay

**Câu chuyện bán:** *"IPC đã trình chủ đầu tư ký nhận rồi — nhưng tiền CĐT
chuyển về đã khớp vào đúng hồ sơ chưa? Với RealtyPro, ngân hàng báo về là
hệ thống tự biết."*

Demo này **không cần tài khoản ngân hàng thật**, chạy được offline.

---

## 0. Chuẩn bị (1 phút, làm trước khi khách vào)

- Đăng nhập dev: https://realtypro.bsdinsights.com
- Chọn hồ sơ demo: mở **Realty Project → Doanh thu → IPC (hồ sơ thanh
  toán)** → mở **IPC/2026/0006** (đã ký, đề nghị CĐT thanh toán **412,5
  tỷ**, đã thu **0**).
- Để sẵn 2 tab: (a) form IPC/2026/0006, (b) **Đối soát ngân hàng → Giao
  dịch ngân hàng**.

> Nếu đã demo lần trước, xem **Mục 4 — Reset** để đưa về 0 đồng.

---

## 1. Chỉ cho khách "trạng thái hiện tại" (30 giây)

Trên form **IPC/2026/0006**, chỉ vào khối giá trị:

| Trường | Giá trị |
|---|---|
| Đề nghị CĐT thanh toán (`amount_net`) | 412,5 tỷ |
| **CĐT đã thu (thực nhận)** | **0 đ** |
| **Còn phải thu** | **412,5 tỷ** |

**Nói:** *"IPC này ký rồi, đề nghị CĐT thanh toán 412,5 tỷ. Nhưng đã thu
được đồng nào chưa? Hiện là 0. Đây là câu mà Excel không tự trả lời — phải
có người ngồi đối chiếu sao kê."*

---

## 2. Mô phỏng CĐT chuyển tiền (1 phút) — đường DEMO tự chứa

Vào **Đối soát ngân hàng → Mô phỏng giao dịch (demo)**. Điền:

| Ô | Giá trị nhập |
|---|---|
| Chiều | Tiền vào |
| Số tiền | `30000000000` (30 tỷ) |
| Ngân hàng | MBBank |
| **Nội dung CK** | `IPC/2026/0006 CDT thanh toan dot 1` |
| Mã (code) | `IPC/2026/0006` *(để trống cũng được — hệ thống đọc trong nội dung)* |

Bấm **Mô phỏng**.

**Nói:** *"Đây là mô phỏng đúng cái ngân hàng bắn về khi CĐT chuyển tiền —
số tiền, nội dung chuyển khoản có ghi mã IPC. Trong thực tế cái này do
SePay/ngân hàng gửi tự động, không ai gõ tay."*

---

## 3. Cho khách thấy hệ thống TỰ KHỚP (điểm chốt — 1 phút)

Sau khi bấm Mô phỏng, form **giao dịch** mở ra. Chỉ vào:

- **Trạng thái = Đã đối soát** (xanh)
- **Đối soát vào = IPC/2026/0006**
- Ghi chú khớp: *"Khớp IPC ... trong nội dung CK"*

**Nói:** *"Không ai bấm khớp cả — hệ thống đọc mã IPC trong nội dung chuyển
khoản và tự gắn vào đúng hồ sơ. Một giao dịch chỉ khớp vào một IPC."*

Quay lại tab **IPC/2026/0006** (bấm F5 nếu cần), chỉ lại khối giá trị:

| Trường | Trước | **Sau** |
|---|---|---|
| CĐT đã thu | 0 | **30 tỷ** |
| Còn phải thu | 412,5 tỷ | **382,5 tỷ** |

Và trong **lịch sử trao đổi** (chatter) của IPC có dòng: *"Nhận 30.000.000.000
từ CĐT qua ngân hàng (MBBank ...) — đã đối soát vào IPC."*

**Nói:** *"IPC tự cập nhật đã thu 30 tỷ, còn phải thu 382,5 tỷ, có ghi vết
trong lịch sử. Đây là vòng khép: ký nhận → tiền về → đối soát, tự động."*

*(Muốn ấn tượng hơn: mô phỏng thêm 1 giao dịch nữa cho cùng IPC → đã thu
cộng dồn lên.)*

---

## 3b. (Tuỳ chọn) Cho thấy nó KHÔNG khớp bừa

Mô phỏng 1 giao dịch **nội dung không có mã IPC** (vd `chuyen tien`):
→ giao dịch để trạng thái **Mới nhận**, không gắn IPC nào.

**Nói:** *"Tiền vào mà không rõ của hồ sơ nào thì hệ thống KHÔNG đoán bừa —
để đó cho người đối soát tay. Không có chuyện khớp nhầm khối lượng vào sai
hồ sơ."*

---

## 4. Reset giữa các lần demo

Xoá giao dịch mô phỏng để `amount_received` về 0:

**Đối soát ngân hàng → Giao dịch ngân hàng** → chọn các dòng vừa tạo (nguồn
= SePay) → **Xoá**. IPC tự tính lại về 0.

*(Xoá giao dịch chỉ gỡ đối soát, KHÔNG đụng gì tới IPC/BBNT.)*

---

## 5. Phiên bản "thật" — SePay Test mode (nếu khách muốn thấy webhook thật)

Thay Mục 2 bằng luồng webhook thật, vẫn không cần tài khoản NH thật:

1. Cấu hình token demo trên hệ thống: Settings → Kỹ thuật → Tham số hệ thống
   → thêm `sepay.webhook.token` = một chuỗi bí mật.
2. Vào **my.sepay.vn → Test mode** → tạo webhook trỏ tới
   `https://realtypro.bsdinsights.com/sepay/webhook`, header
   `Authorization: Apikey <token>`.
3. SePay Test mode → **Mô phỏng giao dịch** (nội dung có mã IPC).
4. SePay bắn webhook thật vào hệ thống → giao dịch xuất hiện y như Mục 3.

**Nói:** *"Đây là đường thật đi vào production — chỉ khác là dùng sandbox
của SePay nên không đụng tài khoản thật."*

---

## Ranh giới cần biết (để trả lời câu hỏi khó của khách)

- **SePay chỉ báo dòng tiền** (tiền vào/ra, nội dung, số dư). Nó **không**
  thay ngân hàng lõi: không có dư nợ vay, lịch trả, bảo lãnh, hạn mức.
  RealtyPro vẫn giữ giấy báo nợ + AI đọc chứng từ cho phần đó.
- **SePay cần liên kết tài khoản ngân hàng của khách.** Với doanh nghiệp tư
  nhân thường OK; khách vốn nhà nước / CĐT lớn có thể không duyệt cho bên
  thứ ba đọc dòng tiền. Vì vậy hệ thống nhận **nhiều nguồn** (SePay / sao kê
  file / AI đọc chứng từ / nhập tay) — ai dùng SePay được thì dùng, không
  thì đường khác vẫn chạy.
- Giao dịch luôn qua **sổ đệm** rồi mới đối soát → khớp nhầm gỡ lại được,
  không sửa vào chứng từ gốc.

---

*Trạng thái: dev, đã verify end-to-end. Menu: "Đối soát ngân hàng" (app cấp
gốc) + khối "CĐT đã thu" trên form IPC.*
