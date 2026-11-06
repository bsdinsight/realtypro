# -*- coding: utf-8 -*-
"""ĐVT của BoQ nhà thầu dùng CHUNG bảng `uom.uom` (việc 1383).

TRƯỚC ĐÂY có hai bảng đơn vị tính: `rp.progress.uom` (BoQ, nghiệm thu —
29 ĐVT trên demo) và `uom.uom` (tài nguyên, định mức, kho, mua sắm). Hai
bảng chỉ trùng 5 tên nên chọn định mức không điền được ĐVT cho dòng BoQ,
và không ai so được ĐVT của dòng BoQ với ĐVT của định mức — trên demo
4/10 dòng có định mức đang lệch nghĩa (m² với Tấn), tức chi phí đang
nhân hai đại lượng khác đơn vị mà không ai báo.

BƯỚC NÀY CHỈ CHUYỂN BoQ NHÀ THẦU. BoQ dự án và nghiệm thu (`rp_progress`)
vẫn ở bảng cũ: `rp_progress` cài ở 9 DB dùng chung thư mục addons, đổi
cột ở đó phải nâng cấp đủ cả 9 cùng lúc. Chỗ hai thế giới gặp nhau — nút
chuyển BoQ trúng thầu sang BoQ dự án — đi qua `progress_uom_from`.

QUY ĐỔI THEO TÊN ĐÃ CHUẨN HOÁ, KHÔNG THEO ID. "m3", "1m³", "Mét khối"
là một; "100m³" là m³ × 100 (Odoo 19 khai bằng đơn vị gốc + hệ số, không
còn nhóm đơn vị). Không tìm thấy thì TẠO trong `uom.uom` với đúng chữ
người dùng đã quen, không ép về một đơn vị gần giống.
"""
import re

from odoo.tools import float_compare

# Tên đã chuẩn hoá → tên chuẩn. Chỉ gom những cách viết CÙNG nghĩa.
ALIASES = {
    'mét khối': 'm³', 'met khoi': 'm³',
    'mét vuông': 'm²', 'met vuong': 'm²',
    'mét dài': 'm', 'met dai': 'm', 'md': 'm', 'mét': 'm', 'meter': 'm',
    'ton': 'tấn', 't': 'tấn', 'tonne': 'tấn',
    'kilôgam': 'kg', 'kilogam': 'kg', 'kilogram': 'kg',
    'pc': 'cái', 'set': 'bộ', 'lot': 'trọn gói',
}

# Đơn vị chuẩn của Odoo — dùng khi DB chưa có ĐVT đang bật cùng tên.
CORE = {
    'm³': 'uom.product_uom_cubic_meter',
    'm²': 'uom.product_uom_square_meter',
    'm': 'uom.product_uom_meter',
    'kg': 'uom.product_uom_kgm',
    'tấn': 'uom.product_uom_ton',
}

# Đơn vị mang TÊN riêng nhưng đo bằng đơn vị gốc: giữ chữ người dùng
# quen, vẫn quy đổi được. (tên chuẩn hoá → (đơn vị gốc, hệ số))
DERIVED = {
    'md khoan': ('m', 1.0),
    'm sâu': ('m', 1.0),
    'cái': ('__unit__', 1.0),
}
_HUNDREDS = re.compile(r'^(\d+(?:[.,]\d+)?)\s*(m³|m²|m)$')


def norm_uom_name(name):
    """Chuẩn hoá tên ĐVT để so: chữ thường, m3→m³, bỏ "1" đứng đầu."""
    s = re.sub(r'\s+', ' ', (name or '').strip().lower())
    s = s.replace('m3', 'm³').replace('m2', 'm²')
    # "1m³", "1 m³", "1md khoan": số 1 đứng đầu chỉ nghĩa là "trên MỘT
    # đơn vị" — "100m³" thì giữ, đó là đơn vị khác.
    s = re.sub(r'^1\s*(?=[^\d.,])', '', s)
    return ALIASES.get(s, s)


def _installed_langs(env):
    # Odoo 19 báo lỗi "Invalid language code" khi đọc tên bằng một ngôn
    # ngữ CHƯA CÀI — không được gọi cứng with_context(lang='vi_VN').
    return [code for code, _name in env['res.lang'].get_installed()]


def uom_names(uom):
    """Mọi bản dịch tên của một ĐVT (theo các ngôn ngữ đã cài), đã chuẩn hoá."""
    if not uom:
        return set()
    names = {norm_uom_name(uom.name)}
    for lang in _installed_langs(uom.env):
        names.add(norm_uom_name(uom.with_context(lang=lang).name))
    names.discard('')
    return names


def same_unit(a, b):
    """Hai ĐVT đo cùng một thứ với cùng độ lớn chưa.

    Trống một bên thì coi như khớp (chưa có gì để so). Khác bản ghi
    nhưng cùng tên chuẩn hoá ("m3" và "m³" do người dùng tạo hai lần) là
    khớp; cùng gốc và cùng hệ số tuyệt đối cũng là khớp.
    """
    if not a or not b or a == b:
        return True
    if uom_names(a) & uom_names(b):
        return True
    return bool(a._has_common_reference(b)
                and float_compare(a.factor, b.factor, precision_digits=6) == 0)


def find_uom(env, key):
    """ĐVT có tên chuẩn hoá = key: ưu tiên bản đang bật, rồi id nhỏ."""
    Uom = env['uom.uom'].with_context(active_test=False)
    found = Uom.search([], order='active desc, id').filtered(
        lambda u: key in uom_names(u))
    return found[:1]


def resolve_uom(env, label, cache=None):
    """`uom.uom` tương ứng với một ĐVT viết bằng chữ — tìm, không có thì tạo."""
    cache = {} if cache is None else cache
    key = norm_uom_name(label)
    if not key:
        return env['uom.uom']
    if key in cache:
        return cache[key]
    Uom = env['uom.uom']

    uom = find_uom(env, key)
    if uom and not uom.active:
        # Odoo 19 cài sẵn m³ nhưng để TẮT; tắt thì ô chọn không đổ ra,
        # người dùng sẽ đi tạo một "m³" thứ ba.
        uom.active = True
    if not uom:
        m = _HUNDREDS.match(key)
        if m:
            base = resolve_uom(env, m.group(2), cache)
            factor = float(m.group(1).replace(',', '.'))
            uom = Uom.create({'name': (label or key).strip(),
                              'relative_uom_id': base.id,
                              'relative_factor': factor})
        elif key in DERIVED:
            base_key, factor = DERIVED[key]
            base = (env.ref('uom.product_uom_unit') if base_key == '__unit__'
                    else resolve_uom(env, base_key, cache))
            uom = Uom.create({'name': (label or key).strip(),
                              'relative_uom_id': base.id,
                              'relative_factor': factor})
        elif key in CORE:
            uom = env.ref(CORE[key], raise_if_not_found=False) or Uom
            if uom and not uom.active:
                uom.active = True
        if not uom:
            uom = Uom.create({'name': (label or key).strip()})
    cache[key] = uom
    return uom


def uom_from_progress(env, progress_uom, cache=None):
    """ĐVT `uom.uom` cho một ĐVT của bảng xây dựng cũ (`rp.progress.uom`)."""
    if not progress_uom:
        return env['uom.uom']
    # Tên tiếng Việt nếu DB có cài tiếng Việt — đó là chữ người dùng gõ.
    vi = ('vi_VN' in _installed_langs(env)
          and progress_uom.with_context(lang='vi_VN').name)
    label = vi or progress_uom.name or progress_uom.code
    return resolve_uom(env, label, cache)


def progress_uom_from(env, uom):
    """Chiều ngược lại — cho BoQ dự án, vẫn ở bảng cũ tới bước `rp_progress`."""
    PU = env['rp.progress.uom'].with_context(active_test=False)
    if not uom:
        return PU
    keys = uom_names(uom)
    for pu in PU.search([], order='active desc, id'):
        if {norm_uom_name(pu.code), norm_uom_name(pu.name)} & keys:
            return pu
    code = (uom.name or '').strip() or 'uom-%s' % uom.id
    if PU.search_count([('code', '=', code)]):
        code = '%s-%s' % (code, uom.id)
    return PU.create({'name': uom.name, 'code': code})
