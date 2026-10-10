# Phát hành bản Odoo 17 cho đối tác

Bốn bước, chạy theo đúng thứ tự. Bước 3 cần một Odoo 17 thật — bản
dịch KHÔNG tự sinh được bằng script, lý do ghi ở `fill_po.py`.

### 1. Sinh bản 17 từ commit (không phải từ thư mục làm việc)

```
git archive HEAD addons/_common | tar -x -C /tmp/src19
python3 tools/port17/port_to_17.py /tmp/src19/addons/_common /tmp/out17 \
        --prev <bản đã giao>/addons
```

`--prev` bắt buộc: công cụ dừng nếu một module đổi mã mà quên tăng
phiên bản — bỏ sót là đối tác nâng cấp không thấy thay đổi, im lặng.

### 2. Đẩy lên máy kiểm và cài thử CẢ 13 MODULE

```
rsync -az --delete /tmp/out17/ <vps>:/root/port17/addons/
```

Cài cả 13, không chỉ bộ trong `test_xboss.sh`: bẫy `group_ids` của
`re_bank_sync` từng lọt đúng vì nó nằm ngoài bộ kiểm.

### 3. Sinh khung .po bằng chính Odoo rồi điền tiếng Việt

```
# trên VPS, DB đã cài bản tiếng Anh ở bước 2:
odoo -d p17po --i18n-export=/mnt/po/<mod>.po --modules=<mod> --stop-after-init
# kéo khung về rồi điền:
python3 tools/port17/fill_po.py <thư mục khung> /tmp/out17
```

Khung do Odoo xuất mới có `#. module:` và `#: model:…` — thiếu chúng
thì bộ nhập của Odoo 17 nổ `AttributeError: 'NoneType' … groups`,
hoặc tệ hơn là nạp êm mà chẳng dịch gì.

Kiểm lại: cài trên DB mới với `--load-language=vi_VN`, rồi soi
`ir_model_fields.field_description->>'vi_VN'` có chữ không.

### 4. Chạy bộ kiểm trên Odoo 17 thật, rồi mới đẩy

```
bash /root/port17/test_xboss.sh     # phải 0 failed 0 error
```

Mỗi bản phát hành là MỘT COMMIT MỚI chồng lên trong repo bàn giao,
không squash. Trước khi đẩy: `git pull` để gộp commit của đối tác —
họ cũng sửa thẳng trong repo đó.
