# Biên bản kiểm thử sơ lược — Bảo lãnh thực hiện hợp đồng (nhận từ nhà thầu)

| | |
|---|---|
| **Module** | `rp_contract_guarantee` 19.0.1.0.0 |
| **Môi trường** | dev.realtypro (DB `dev`) |
| **Ngày** | 07/07/2026 |
| **Commit** | `511608e` |
| **Kết luận** | ✅ **ĐẠT** — toàn bộ vòng đời lõi chạy đúng |

Sổ đăng ký tập trung các bảo lãnh nhà thầu phụ nộp về (thực hiện HĐ · tạm ứng · bảo hành), tổng thầu là **bên thụ hưởng**. Độc lập với Quản lý Vay.

---

## 1. Phạm vi kiểm thử

Kiểm thử tính năng ghi nhận và quản lý bảo lãnh nhà thầu phụ nộp cho tổng thầu: tạo chứng thư, upload tài liệu, theo dõi hạn, gia hạn, yêu cầu thanh toán khi vi phạm.

**Căn cứ nghiệp vụ:** Luật Đấu thầu 2023 (bảo đảm thực hiện HĐ 2–10% giá trị hợp đồng; hiệu lực đến khi hoàn thành nghĩa vụ / chuyển bảo hành) và Thông tư 11/2022/TT-NHNN.

> **Phân biệt 2 chiều bảo lãnh.** Tính năng này quản lý bảo lãnh mình **NHẬN** từ nhà thầu phụ (không ăn hạn mức, không phát sinh phí cho mình). Khác với "Chứng thư BL" bên Quản lý Vay là bảo lãnh mình **PHÁT HÀNH** (ăn hạn mức tín dụng). Kiểm thử xác nhận hai chiều chạy song song, không xung đột.

---

## 2. Kịch bản kiểm thử thủ công

Đường đi để team làm lại trên dev. Mỗi ca ghi bước thao tác và kết quả mong đợi.

### TC-01 — Tạo bảo lãnh mới từ hợp đồng nhà thầu · ✅ Đạt
- **Bước:** HĐ nhà thầu → tab *"Bảo lãnh nhận (nhà thầu)"* → thêm dòng. Chọn loại (thực hiện HĐ), hình thức (thư BL ngân hàng), bên phát hành, giá trị, ngày hết hạn.
- **Mong đợi:** Tạo được chứng thư; nhà thầu & dự án tự điền từ HĐ; bên thụ hưởng mặc định là công ty mình.

### TC-02 — Kiểm tra % giá trị HĐ + cảnh báo 2–10% · ✅ Đạt
- **Bước:** Nhập giá trị bảo lãnh; xem trường *"% giá trị HĐ"*. Thử giá trị <2% hoặc >10%.
- **Mong đợi:** % tự tính; hiện cảnh báo *"ngoài 2–10%"* khi ngoài ngưỡng (chỉ với loại thực hiện HĐ).

### TC-03 — Kích hoạt & tình trạng hạn · ✅ Đạt
- **Bước:** Bấm *"Kích hoạt"*. Xem trường *"còn (ngày)"* và badge tình trạng hạn.
- **Mong đợi:** Trạng thái → Hiệu lực; badge Còn hiệu lực / Sắp hết hạn (≤30 ngày) / Đã hết hạn theo ngày.

### TC-04 — Upload thư bảo lãnh · ✅ Đạt
- **Bước:** Mở tab *"Tài liệu"* → đính kèm PDF/scan thư bảo lãnh.
- **Mong đợi:** File lưu vào chứng thư; xem/tải lại được.

### TC-05 — Gia hạn qua phụ lục · ✅ Đạt
- **Bước:** Tab *"Phụ lục"* → thêm dòng loại *"Gia hạn"*, nhập ngày hết hạn mới.
- **Mong đợi:** Ngày hết hạn chứng thư cập nhật ngay; ghi chatter cũ→mới; tình trạng hạn tính lại.

### TC-06 — Yêu cầu thanh toán (claim) khi nhà thầu vi phạm · ✅ Đạt
- **Bước:** Bấm *"Yêu cầu thanh toán"* → nhập số tiền + lý do.
- **Mong đợi:** Trạng thái → Đã yêu cầu thanh toán; chặn số tiền vượt giá trị BL; ghi chatter.

### TC-07 — Cảnh báo sắp hết hạn (cron) · ✅ Đạt
- **Bước:** Cron *"Bảo lãnh HĐ: cảnh báo sắp hết hạn"* (07:30 hằng ngày) hoặc chạy tay.
- **Mong đợi:** Tạo activity nhắc cho người phụ trách HĐ với các BL hết hạn trong 30 ngày; không tạo trùng.

### TC-08 — Chạy song song với "Chứng thư BL" (Quản lý Vay) · ✅ Đạt
- **Bước:** Trên form HĐ nhà thầu, xem 2 smart button *"BL nhận"* và *"Chứng thư BL"*.
- **Mong đợi:** Hai chiều đếm độc lập, mở đúng danh sách riêng; không xung đột form.

---

## 3. Kết quả kiểm thử tự động (odoo shell, DB dev)

| Hạng mục | Số liệu quan sát | Kết quả |
|---|---:|---|
| Migrate field bảo lãnh phẳng cũ → bản ghi | 3 bản ghi | ✅ Đạt |
| % giá trị HĐ (BL 6,804 tỷ / HĐ 97,2 tỷ) | 7,00 % | ✅ không cảnh báo |
| Kích hoạt → tình trạng hạn (hết hạn +15 ngày) | Sắp hết hạn · 15 ngày | ✅ Đạt |
| Gia hạn phụ lục +6 tháng | → 07/01/2027 | ✅ Còn hiệu lực |
| Yêu cầu thanh toán (claim) | 6.804.000.000 đ | ✅ Đã yêu cầu TT |
| Cron cảnh báo hết hạn | 1 activity | ✅ Đạt |
| Coexist bridge — BL nhận / Chứng thư BL | 3 / 1 | ✅ độc lập |

---

## 4. Ghi chú & giới hạn

- **12 field bảo lãnh phẳng cũ** trên hợp đồng vẫn hiển thị ở tab *"Bảo lãnh"* (đã migrate sang bản ghi nên hiện trùng lặp). Đề xuất một bản cleanup riêng để ẩn/gộp — chưa gỡ vì tab này đang được module cầu nối (`rp_guarantee_bridge`) trang trí.
- Kiểm thử chạy trên **dữ liệu demo dev**; chưa chạy trên chứng từ thật của khách. Khi triển khai nên chạy thử với vài bộ chứng thư thật để hiệu chỉnh.
- Cài đặt sạch trên cả 4 DB: `dev`, `demo`, `greenhills`, `xboss`.
- **Menu:** `Dự án → Bảo lãnh HĐ nhà thầu` và báo cáo `Bảo lãnh sắp / đã hết hạn`.

---

*RealtyPro · rp_contract_guarantee 19.0.1.0.0 · Biên bản kiểm thử sơ lược · nội bộ*
