# Realty - Document

> 🚧 **Status: Placeholder / Work In Progress**

## Scope (planned)

Abstract document model that any RealtyPro entity (project, unit, contract, work order, handover batch...) can attach documents to. Covers document types, versioning, expiry, sign workflow integration, and template rendering. Each sub-suite extends with its own document types: Sales adds HĐMB / Booking Form, Project adds BOQ Signed / Daily Report, Living adds Service Fee Invoice / Maintenance Acceptance.

## Planned models

- `re.document`
- `re.document.type`
- `re.document.template`
- `re.document.version`

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

- `rs_operations — HĐMB, Booking forms, deposit receipts`
- `rp_handover — Handover protocol, punch-list reports`
- `rp_construction — Daily reports, weather logs, photos`
- `rp_boq — Signed BOQ, budget approvals`
- `rl_service_fee — Monthly invoices, payment receipts`
- `rl_maintenance — Acceptance reports, work orders`
- `rl_complaint — Complaint records, resolution proofs`
