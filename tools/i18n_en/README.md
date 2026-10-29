# Bản tiếng Anh của EAMOne (song ngữ)

Hệ thống chạy **hai ngôn ngữ cùng lúc**: mã nguồn giữ nguyên tiếng Việt,
bản tiếng Anh nằm ở `<module>/i18n/en_GB.po`. Người dùng đổi ngôn ngữ
trong hồ sơ cá nhân là thấy tiếng Anh; không ai phải bảo trì hai bản mã.

## Vì sao là `en_GB` chứ không phải `en_US`

Odoo coi chuỗi viết trong mã là **ngôn ngữ nguồn**, và cất nó dưới khoá
`en_US`. Mã của ta viết tiếng Việt, nên với Odoo `en_US` = tiếng Việt —
không ghi bản dịch tiếng Anh vào đó được, ghi vào là ĐÈ MẤT bản gốc.
`en_GB` là một ngôn ngữ đích bình thường, nên dùng nó làm chỗ chứa bản
tiếng Anh.

Hệ quả phải biết: tài khoản để mặc định `en_US` vẫn thấy **tiếng Việt**.
Muốn tiếng Anh thì chọn đúng mục *English (UK)*.

Cách khác là lật nguồn sang tiếng Anh rồi để tiếng Việt ở `vi_VN.po` —
chuẩn Odoo hơn, nhưng đổi toàn bộ mã của 102 module và đẩy hết phần văn
tiếng Việt (trợ giúp, câu báo lỗi — phần viết kỹ nhất) ra khỏi mã. Đã
cân nhắc và KHÔNG chọn; xem thêm `tools/port17/i18n.py`.

## Bốn bước

### 1. Bật ngôn ngữ (một lần cho mỗi DB)

```
odoo i18n loadlang -c <conf> -d <db> -l en_GB
```

### 2. Xuất khung .po — phải do CHÍNH Odoo xuất

```
odoo i18n export -c <conf> -d <db> <module...> -l en_GB -o /tmp/eam_en.po
```

**Đừng tự viết .po.** Bộ nhập của Odoo dựa vào dòng tham chiếu
`#: model:…` / `model_terms:…` / `code:…` để biết bản dịch thuộc trường
nào, view nào. Tệp viết tay thiếu chúng thì hoặc nổ khi nạp, hoặc tệ hơn
— nạp êm mà không dịch được gì.

Lưu ý thứ tự tham số: `-l en_GB` phải đứng **sau** danh sách module, nếu
không argparse nuốt luôn danh sách module vào `-l`.

Và thư mục addons gắn vào container ở chế độ **chỉ đọc**, nên không dùng
được kiểu xuất-ra-từng-module; xuất gộp một tệp rồi để `sinh_po.py` tách.

### 3. Đánh số và dịch

```
python3 tach_va_liet_ke.py /tmp/eam_en.po can_dich.json can_dich.txt
```

Chuỗi cần dịch được đánh số trong `idx.json`. Bản dịch viết vào
`dich/<module>.tsv`, mỗi dòng `<số><TAB><tiếng Anh>` — **không chép lại
chuỗi tiếng Việt**, vì chép tay là mời lỗi chính tả âm thầm: sai một dấu
là msgid không khớp và bản dịch im lặng không áp.

Chuỗi VỐN ĐÃ tiếng Anh (trường kế thừa của `mail.thread`: *Action
Needed*, *Followers*…) bị lọc ra, không dịch lại — dịch lại là đè bản
dịch sẵn có của Odoo lõi.

### 4. Sinh .po rồi nạp

```
python3 sinh_po.py /tmp/eam_en.po dich
rsync -az <addons>/ <vps>:/root/realtypro/addons/ --include='*/' --include='i18n/***' --exclude='*'
odoo i18n import -c <conf> -d <db> -w -l en_GB <đường dẫn .po>
```

`sinh_po.py` **dừng** khi chỗ thay số (`%s`, `%(ten)s`, `%(n)d`) trong
bản dịch lệch với bản gốc. Đây không phải sự cầu toàn: lệch chỗ thay số
thì Odoo nổ `TypeError` đúng lúc người dùng bấm, không phải lúc nạp —
lỗi chỉ lộ trên máy khách.

## Thuật ngữ đã chốt

Giữ nhất quán, vì ba module dùng chung một từ mà dịch ba kiểu là người
đọc tưởng ba thứ khác nhau.

| tiếng Việt | tiếng Anh |
|---|---|
| vị trí | location |
| vị trí chức năng | functional location |
| tài sản | asset |
| cấu phần | component |
| thiết bị chính | main equipment |
| cây lắp ráp | assembly tree |
| nhà máy | plant |
| tổ máy | unit |
| biến tần | **inverter** (không phải "frequency converter") |
| hộp gom chuỗi | string combiner box |
| dàn pin quang điện | PV array |
| khoảng dừng / sổ dừng máy | outage / outage log |
| quy trách nhiệm | responsibility (attribution) |
| loại thời gian | time category |
| khả dụng | availability |
| sản lượng | energy / generation |
| tổn thất | loss |
| cắt giảm | curtailment |
| giờ-máy | unit-hours |
| đếm đúp | double counting |
| quay vòng | rotable |
| đại tu | overhaul |
| tân trang | refurbished |
| phụ tùng | spare part |
| lệnh công việc | work order |
| bảo trì phòng ngừa | preventive maintenance |
| nghiệm thu | acceptance |
| cam kết | commitment |
| phạt | penalty |
| kỳ | period |
| mức quan trọng / trọng yếu | criticality |
| đường cong công suất | power curve |
| điểm đo | measurement point (tag) |
| trạm nâng áp | step-up substation |

## Tiến độ

`idx.json` có **3.919** chuỗi cần dịch cho 30 module EAMOne. Đếm số dòng
trong `dich/*.tsv` là biết đã xong bao nhiêu.

## Chạy trên `aip` (stack tenants) — ba chỗ vấp

1. **Đúng máy chủ PG.** `aip` tồn tại trên CẢ `realtypro-db` lẫn
   `realtypro-ent-db`; bản thật là **`realtypro-ent-db`**. Trỏ nhầm thì
   `odoo -u` vẫn in `Registry loaded` và trả **EXIT=0** mà không làm gì,
   còn `i18n export` báo *"No valid module has been provided"* — thông
   báo ấy nghĩa là "module không installed trong DB vừa kết nối", không
   phải sai đường addons.
2. **Tệp cấu hình riêng, đặt ở chỗ ghi được.** `/etc/odoo/odoo.conf`
   không có `db_password` (lúc chạy server entrypoint mới nạp), và
   `/tmp` trong container thuộc root còn tiến trình chạy bằng `odoo`.
   Dùng `/var/lib/odoo`:
   ```
   docker exec realtypro-tenants-odoo sh -lc 'D=/var/lib/odoo
     cp /etc/odoo/odoo.conf $D/i18n.conf
     printf "db_password = %s\n" "$PASSWORD" >> $D/i18n.conf
     odoo i18n export -c $D/i18n.conf -d aip <mod> -l en_GB -o $D/x.po'
   ```
   Thêm `db_host` vào tệp ĐÃ có dòng `db_host` thì configparser nổ
   `DuplicateOptionError` — sửa bằng `sed`, đừng nối thêm.
3. **Chuỗi JS/XML cần `_t`, chuỗi Python cần `_()`.** Bộ xuất chỉ thấy
   chuỗi nằm trong hai hàm đó. Chuỗi trần trong `.js`, và chuỗi viết
   trong biểu thức `t-esc` của khuôn mẫu OWL, **không bao giờ** ra
   `.po` — nhìn `.po` thấy ít chuỗi bất thường thì đọc lại nguồn trước
   khi kết luận "màn này đã tiếng Anh". Và đừng nối chuỗi từ nhiều mẩu
   dịch rời: gộp cả câu vào một chuỗi có chỗ thay số, để thứ tự từ đổi
   được theo ngôn ngữ.
