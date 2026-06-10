{
    'name': 'Realty - Integration Hub',
    'version': '19.0.0.1.1',
    'category': 'Realty',
    'summary': 'Webhook + API key infrastructure used by RealtyPro to '
               'sync data between the Project, Sales, and Living '
               'databases of one customer.',
    'description': """
Cross-app integration plumbing for RealtyPro.

Each customer runs three Odoo databases (sales / project / living)
on the same stack. Some events span boundaries — e.g. when Project
hands a building over, Sales needs to start selling units; when Sales
records a contract handover, Living needs to onboard the resident.

This module ships the underlying primitives:

* **Outbound webhook queue** — a model + cron that delivers events to
  configured target URLs with HMAC signatures and retry/backoff.
* **Inbound endpoint** — a generic controller at
  ``/realtypro/webhook/<event>`` that authenticates via API key,
  verifies HMAC, deduplicates by event_id, and hands off to a
  registered handler.
* **API key registry** — issue, rotate, and revoke keys per consumer.
* **Audit log** — every inbound and outbound event recorded.

It does NOT define any actual cross-app events. Concrete integrations
live in the app suites (e.g. ``rp_handover`` posts a ``project.handover``
event; the Sales side registers a handler).
    """,
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': ['base', 'mail'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/cron.xml',
        'views/api_key_views.xml',
        'views/webhook_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
