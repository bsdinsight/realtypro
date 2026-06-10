# -*- coding: utf-8 -*-
{
    "name": "Realty - Pricing Base (Reserved)",
    "version": "19.0.2.0.0",
    "category": "Realty/Foundation",
    "summary": "RESERVED: revenue pricing primitives for Realty CRM Phase 4",
    "description": """
Realty - Pricing Base (Reserved Module)
========================================

**STATUS: Not installable in current release.**

This module is reserved for revenue-side pricing primitives that will
land with **Realty CRM Phase 4 (HĐMB — Hợp đồng Mua Bán)**:

- Formula DSL for sale-price calculation
  (e.g. ``unit_price = base × (1 - discount) - cash_discount + furniture × (1 + VAT)``)
- Currency rounding rules (VND: no decimals; USD: 2 decimals)
- VAT computation per company settings and product category
- Discount-stacking math (multiple campaign overlays, priority order)
- Date-based price interpolation (price list valid over time)
- Multi-currency conversion at booking-time vs payment-time

Until Realty CRM Phase 4 ships, this module is empty and
``installable: False``. The folder + manifest remain in the
repo to preserve the namespace and git history.

Historical note
---------------

In v1.1 of Realty Project, this module owned the cost-management
schema (rp.cost.category, re.structure). That was a scope mismatch
the v1.4 design corrected by moving cost models to ``rp_cost_base``
and reserving this module for revenue pricing only. See
``realty_project_cost_schema_v1.4.md`` for the full rationale.

If your DB has v1.1 of this module installed, upgrading to v1.4
will run the pre-migrate script which drops the v1.1 tables and
ir_model_data ownership. The module then becomes inert.

Re-activation
-------------

When Realty CRM Phase 4 development starts:

1. Flip ``installable: True``
2. Add models: ``re.pricing.formula``, ``re.pricing.list``,
   ``re.currency.round.rule``, ``re.discount.stack``
3. Bump version to ``19.0.3.0.0``
4. Re-add to depends of ``rs_operations`` (HĐMB calculations)
   and optionally ``rl_service_fee`` (monthly fee math)
""",
    "author": "BSDInsight",
    "website": "https://bsdinsight.com",
    "license": "AGPL-3",
    "depends": [
        "re_base",
        "mail",
    ],
    "data": [
        "security/ir.model.access.csv",
    ],
    "application": False,
    "installable": False,
}
