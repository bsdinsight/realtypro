# Realty - Vendor

> 🚧 **Status: Placeholder / Work In Progress**

## Scope (planned)

Single source of truth for all vendors and contractors a real-estate operator works with. The same vendor record can act as construction contractor (Project), service provider (Living maintenance), broker partner (Sales distribution), or supplier of any kind. Sub-suites extend the base model with role-specific fields: rp_contractor adds construction license + KPI, rl_maintenance adds SLA + service categories, rs_distributor_portal adds commission tier.

## Planned models

- `re.vendor`
- `re.vendor.category`
- `re.vendor.evaluation`

## Why it ships now

This module is shipped as a manifest-only skeleton so other modules
can declare it as a dependency today. When the implementation lands,
the dependent modules pick up the new models automatically without
any change to their own manifests.

## When implementing

1. Add real models under `models/`, expose via `__init__.py`.
2. Add views under `views/` and reference them in the manifest's `data` list.
3. Add `security/<module>.xml` with groups + record rules; expand
   `security/ir.model.access.csv`.
4. If user-facing menus are needed, declare them under a category that
   makes sense to the operator (e.g. Settings → Realty → Documents).
5. Add tests under `tests/`.
6. Bump version (e.g. `19.0.1.0.0`).
7. Replace this README with implementation docs.

## Consumers

The following modules will depend on this once implemented; sketches
included so future work can be planned coherently:

- `rp_contractor — Construction contractors, KPI`
- `rl_maintenance — Service providers (cleaning, security, repairs)`
- `rs_distributor_portal — Broker partners, commission tiers`
