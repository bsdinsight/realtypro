# Realty Pro — Community Edition

> Open-source Odoo 19 suite for Vietnamese real estate developers & construction companies.
> Quản lý dự án bất động sản, hợp đồng nhà thầu, nghiệm thu khối lượng, vay vốn & bảo lãnh ngân hàng.

[![Tests](https://github.com/bsdinsight/realtypro/actions/workflows/test.yml/badge.svg)](https://github.com/bsdinsight/realtypro/actions/workflows/test.yml)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Odoo](https://img.shields.io/badge/Odoo-19-714B67.svg)](https://www.odoo.com)

---

## Tính năng

Realty Pro Community Edition bao gồm các module foundation cho doanh nghiệp BĐS / xây dựng:

### Quản lý vay vốn — `re_loan`
- HĐ tín dụng (HĐTD) → Hạn mức (Facility) → Khế ước nhận nợ (KW)
- Giải ngân + Trả nợ + Lịch lãi tự động (declining / flat, act/365 / act/360 / 30/360)
- Phụ lục KW (gia hạn, đổi lãi suất, cơ cấu nợ)
- Tài sản thế chấp (multi-pledge), Vay nội bộ (on-lending)
- Báo cáo: dư nợ, đến hạn, aging, kế hoạch thanh toán theo năm

### Bảo lãnh ngân hàng — `re_guarantee`
- Đề nghị phát hành BL (Nháp → Kích hoạt → Phát hành)
- Chứng thư BL (Phát hành → Tất toán auto khi đủ phí + ký quỹ + phạt + tiền gốc)
- 6 loại BL chuẩn VN: dự thầu, thực hiện HĐ, tạm ứng, bảo hành, thanh toán, khác
- Auto khôi phục hạn mức facility khi tất toán
- Theo dõi phí + ký quỹ + phạt trả chậm

### Quản lý dự án xây dựng — `rp_*`
- Cấu trúc dự án: Project → Subzone → Building → Structure
- Gói thầu (Tender Package) + BOQ + Dự toán
- HĐ nhà thầu: BOQ, mốc thanh toán, phụ lục, biến đổi
- Tiến độ thi công + BBNT (Biên Bản Nghiệm Thu) + Hóa đơn nhà thầu
- Bridge: phân bổ vay vốn theo dự án × mục đích × hạng mục

### Foundation — `re_*`
- Master data (đối tác, ngân hàng, đơn vị hành chính VN), document, vendor, integration hub

---

## Limits Community Edition

> ⚠️ **Free tier capped**: 1 dự án · 1 hợp đồng nhà thầu · 500 tasks tiến độ.
>
> Để unlock unlimited + advanced features (Bryntum Gantt, EVM reports, Contractor Hub marketplace,
> Excel/MPP import, multi-bank reconciliation, audit & compliance, SLA support), nâng cấp lên
> [Realty Pro Enterprise](https://bsdinsight.com/realtypro).

---

## Cài đặt

### Yêu cầu
- Odoo 19 Community
- PostgreSQL 16+
- Python 3.10+

### Docker (khuyến nghị)

```bash
git clone https://github.com/bsdinsight/realtypro.git
cd realtypro
docker compose up -d
```

`docker-compose.yml` mẫu:

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: odoo
      POSTGRES_PASSWORD: odoo
      POSTGRES_DB: postgres

  odoo:
    image: odoo:19
    depends_on: [db]
    ports: ["8069:8069"]
    volumes:
      - ./addons/_common:/mnt/extra-addons/_common
      - ./addons/_project:/mnt/extra-addons/_project
    command: >
      odoo
      --db_host=db --db_user=odoo --db_password=odoo
      --addons-path=/usr/lib/python3/dist-packages/odoo/addons,/mnt/extra-addons/_common,/mnt/extra-addons/_project
```

### Cài module
Vào Apps → Update Apps List → cài theo thứ tự:
1. `re_loan` (vay vốn) — kéo theo `re_base`, `re_party`, `re_master_data`
2. `re_guarantee` (bảo lãnh NH)
3. `rp_contractor` → `rp_cost_base` → `rp_estimate` → `rp_contract` → `rp_progress`
4. `rp_loan_bridge` + `rp_guarantee_bridge` (tích hợp vay × dự án)

---

## Kiến trúc

```
addons/
├── _common/                       # Foundation modules (re_*)
│   ├── re_base/                   # Auth, groups, base classes
│   ├── re_party/                  # res.partner extensions (is_bank, is_contractor)
│   ├── re_master_data/            # Master data: bank list, document types
│   ├── re_document/               # Document registry
│   ├── re_vendor/                 # Vendor master (placeholder)
│   ├── re_integration_hub/        # Hub integration patterns
│   ├── re_loan/                   # Loan management core
│   ├── re_loan_account/           # Accounting integration cho loan
│   ├── re_guarantee/              # Bank guarantee management
│   ├── re_pricing_base/           # Pricing utilities
│   └── vn_administrative_units/   # VN provinces/districts/wards
└── _project/                      # Realty Project modules (rp_*)
    ├── rp_contractor/             # Contractor master
    ├── rp_cost_base/              # Cost categories, structures
    ├── rp_estimate/               # Tender package, BOQ, estimate
    ├── rp_contract/               # Contractor contract management
    ├── rp_progress/               # Construction progress + BBNT
    ├── rp_loan_bridge/            # Phân bổ vay × dự án × mục đích
    └── rp_guarantee_bridge/       # Link BL ↔ HĐ nhà thầu
```

---

## Đóng góp

Đóng góp được hoan nghênh! Vui lòng:
1. Đọc [CONTRIBUTING.md](./CONTRIBUTING.md)
2. Ký CLA (Contributor License Agreement) — bot sẽ tự kiểm tra trên PR
3. Mở issue trước khi gửi PR lớn để thảo luận thiết kế

Code style: PEP 8 + Odoo guidelines. Test bắt buộc cho new feature.

---

## License

```
Copyright (C) 2026 BSDInsight (Vietnam)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Affero General Public License for more details.
```

Full text: [LICENSE](./LICENSE) · [AGPL-3.0 summary](https://choosealicense.com/licenses/agpl-3.0/)

**Dual licensing**: BSDInsight retains copyright và cấp Realty Pro Enterprise dưới license proprietary
(OPL-1) cho khách hàng muốn tránh AGPL obligations. Liên hệ: sales@bsdinsight.com.

---

## Liên hệ

- Website: https://bsdinsight.com
- Email: hello@bsdinsight.com
- Issues: https://github.com/bsdinsight/realtypro/issues
- Discussions: https://github.com/bsdinsight/realtypro/discussions
