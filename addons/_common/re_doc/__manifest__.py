# -*- coding: utf-8 -*-
{
    "name": "Realty - Doc Template",
    "version": "19.0.1.0.0",
    "summary": "Mẫu tài liệu Word (.docx) mail-merge cho hồ sơ Realty",
    "description": """
Realty - Doc Template
=====================

Soạn mẫu hợp đồng / phụ lục / biên bản bằng Word (.docx) với placeholder
Jinja2, rồi kết xuất tài liệu đã điền dữ liệu từ một hồ sơ bất kỳ
(hợp đồng mua bán, đặt cọc, phụ lục, phiếu thu...).

Tầng A — render engine (docxtpl). Tầng B (soạn template ngay trong
trình duyệt qua OnlyOffice) bổ sung sau.

Kiến trúc port từ Doc Engine của Parkone.
""",
    "author": "BSD Insight",
    "website": "https://bsdinsight.com",
    "category": "Realty/Core",
    "license": "LGPL-3",
    "depends": ["base", "mail", "re_base"],
    "data": [
        "security/ir.model.access.csv",
        "views/doc_template_views.xml",
        "wizard/doc_render_wizard_views.xml",
        "views/doc_template_onlyoffice_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "re_doc/static/src/onlyoffice_editor/onlyoffice_editor.scss",
            "re_doc/static/src/onlyoffice_editor/onlyoffice_editor.js",
            "re_doc/static/src/onlyoffice_editor/onlyoffice_editor.xml",
        ],
    },
    "application": False,
    "installable": True,
}
