#!/usr/bin/env python3
"""Đối chiếu mọi đường dẫn menu viết trong tài liệu với cây menu THẬT.

Vì sao cần: tài liệu ghi "Vào **A → B → C**" là một hợp đồng với người
đọc. Menu bị gom lại hay đổi tên thì câu đó thành sai, mà không có test
nào đổ — người dùng mới là người phát hiện. Đã dính đúng lỗi này: sau
đợt gom menu, root "Đối soát ngân hàng" bị tắt và các mục con chuyển
sang "Vốn & Ngân quỹ → Chứng từ & tiền từ NH", nhưng tài liệu vừa viết
xong vẫn ghi đường cũ.

Phải nạp CẢ menu đã tắt, gắn cờ ON/OFF. Bản đầu chỉ nạp menu đang bật
và vì thế KHÔNG bắt được chính lỗi nói trên: root đã tắt thì vế đầu
không khớp menu gốc nào, chuỗi bị coi là "không phải đường dẫn menu" và
đi qua im lặng. Menu đã tắt là bằng chứng mạnh nhất rằng tài liệu đang
mô tả một giao diện không còn tồn tại — phải báo to nhất, không phải bỏ
qua. Một nhánh cha tắt thì mọi mục con coi như tắt theo.

  docker exec <pg> psql -U odoo -d <db> -tAc "
  WITH RECURSIVE t AS (
    SELECT id,parent_id,coalesce(name->>'vi_VN',name->>'en_US') nm,
           coalesce(name->>'vi_VN',name->>'en_US') p, active
    FROM ir_ui_menu WHERE parent_id IS NULL
    UNION ALL
    SELECT m.id,m.parent_id,coalesce(m.name->>'vi_VN',m.name->>'en_US'),
           t.p||' → '||coalesce(m.name->>'vi_VN',m.name->>'en_US'),
           (m.active AND t.active)
    FROM ir_ui_menu m JOIN t ON m.parent_id=t.id)
  SELECT (CASE WHEN active THEN 'ON  ' ELSE 'OFF ' END)||p FROM t
  ORDER BY p;" > menu_paths.txt

Dùng: python3 tools/check_menu_paths.py menu_paths.txt docs/user_guide
"""
import pathlib
import re
import sys

# Chỉ soi chuỗi in đậm có mũi tên — đó là quy ước ghi đường dẫn menu.
#
# Nhận diện "đây có phải đường dẫn menu không" KHÔNG dựa vào vế đầu.
# Hai bản trước đều đòi vế đầu phải là một menu gốc có thật, và cả hai
# lần đều mù đúng chỗ nguy hiểm nhất:
#   • bản 1 — root bị TẮT  → vế đầu không khớp gốc nào → bỏ qua im lặng;
#   • bản 2 — root bị ĐỔI TÊN tại chỗ ("Quản lý Vay" → "Vốn & Ngân quỹ")
#     → tên cũ biến mất hẳn khỏi cây, không ON cũng không OFF → lại bỏ
#     qua im lặng, đúng loại đường dẫn cần bắt nhất.
# Quy tắc mới: chỉ cần MỘT đoạn bất kỳ trùng tên một menu có thật thì
# coi là đường dẫn menu và soát tới cùng. Chuỗi mũi tên không dính menu
# nào ("Nháp → Hiệu lực", "lãi → phí → gốc") vẫn tự rơi ra ngoài.
BOLD_ARROW = re.compile(r'\*\*([^*\n]*?→[^*\n]*?)\*\*')
SPLIT = re.compile(r'\s*→\s*')


def main(tree_file, docs_dir):
    live, dead = [], []
    for line in pathlib.Path(tree_file).read_text(
            encoding='utf-8').splitlines():
        line = line.strip()
        if line.startswith('ON '):
            live.append(line[3:].strip())
        elif line.startswith('OFF '):
            dead.append(line[4:].strip())
    if not live:
        print('  ! file cây menu rỗng hoặc thiếu cờ ON/OFF')
        return 2

    known, off = set(live), set(dead)
    roots = {p.split(' → ')[0] for p in live}
    # MỌI tên menu ở mọi cấp, kể cả menu đã tắt — dùng để nhận diện
    # "chuỗi này đang nói về menu", không dùng để kết luận đúng/sai.
    names = {seg for p in live + dead for seg in p.split(' → ')}

    bad = 0
    for mdx in sorted(pathlib.Path(docs_dir).rglob('*.mdx')):
        for i, line in enumerate(
                mdx.read_text(encoding='utf-8').splitlines(), 1):
            for m in BOLD_ARROW.finditer(line):
                parts = [p.strip(' .:*') for p in SPLIT.split(m.group(1))]
                parts = [p for p in parts if p]
                if len(parts) < 2 or not (set(parts) & names):
                    continue          # không dính menu nào → không soi
                chain = ' → '.join(parts)
                if chain in known:
                    continue
                if chain in off:
                    why = 'MENU ĐÃ TẮT'
                elif parts[0] not in roots:
                    why = ('VẾ ĐẦU "%s" KHÔNG PHẢI MENU GỐC (đổi tên? '
                           'viết tắt đường dẫn?)' % parts[0])
                else:
                    why = 'KHÔNG CÓ'
                tail = parts[-1]
                hint = [p for p in live
                        if p.endswith(' → ' + tail) or p == tail][:2]
                print('  SAI (%s)\n       %s:%d\n       viết: %s'
                      % (why, mdx, i, chain))
                for h in hint:
                    print('       thật: %s' % h)
                if not hint:
                    print('       (không có mục "%s" nào đang bật)' % tail)
                bad += 1
    print('  không có đường dẫn menu sai' if not bad
          else '  %d đường dẫn sai' % bad)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2]))
