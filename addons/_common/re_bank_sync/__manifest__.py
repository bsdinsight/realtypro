# -*- coding: utf-8 -*-
{
    'name': 'Realty - Bank Sync (SePay)',
    'version': '19.0.1.0.1',
    'category': 'Realty/Finance',
    'summary': 'Sổ đệm giao dịch ngân hàng + webhook SePay + đối soát. '
               'Nguồn-bất-khả-tri: SePay / file / AI / thủ công.',
    'description': """
Realty - Bank Sync
==================

Tầng đệm nhận giao dịch ngân hàng và đối soát vào chứng từ (IPC thu tiền,
đặt cọc, trả nợ vay...). **Nguồn cắm được** — không khoá vào SePay:

- `re.bank.transaction` — sổ giao dịch ngân hàng, chống trùng, có raw payload.
- Webhook SePay — nhận realtime, tái dùng hạ tầng re_integration_hub
  (re.webhook.log chống trùng + re.api.key xác thực).
- Nút "Mô phỏng giao dịch" — demo tự chứa, không cần tài khoản NH thật.

Đối soát IPC để module bridge riêng (không khoá _common vào rp_owner_contract).
""",
    'author': 'BSDInsight',
    'website': 'https://realtypro.vn',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 're_integration_hub'],
    'data': [
        'security/ir.model.access.csv',
        # views TRƯỚC wizards: wizards/sepay_simulate_views.xml gắn menu vào
        # menu_re_bank_sync_root khai trong views/ — đảo thứ tự thì cài mới
        # sẽ nổ "External ID not found" (cài lại trên DB đã có menu thì
        # không lộ, nên lỗi chỉ xuất hiện ở DB sạch).
        'views/re_bank_transaction_views.xml',
        'wizards/sepay_simulate_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
