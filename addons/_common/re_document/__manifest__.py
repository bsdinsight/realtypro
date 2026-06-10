# -*- coding: utf-8 -*-
{
    "name": "Realty - Documents",
    "version": "19.0.0.1.1",
    "category": "Realty",
    "summary": "🚧 Đang phát triển - Shared document registry across all sub-suites",
    "description": """
Realty - Document
=================

Abstract document model that any RealtyPro entity (project, unit, contract, work order, handover batch...) can attach documents to. Covers document types, versioning, expiry, sign workflow integration, and template rendering. Each sub-suite extends with its own document types: Sales adds HĐMB / Booking Form, Project adds BOQ Signed / Daily Report, Living adds Service Fee Invoice / Maintenance Acceptance.

**Status: Placeholder / Work In Progress.**

Planned models:
  - re.document
  - re.document.type
  - re.document.template
  - re.document.version

This module ships as a skeleton so other modules can declare it as a
dependency today and start using its (eventual) APIs. Until the
implementation lands, installing this module only adds the manifest
record; no models or menus are created.
""",
    "author": "BSDInsight",
    "website": "https://bsdinsight.com",
    "license": "AGPL-3",
    "depends": ['re_base', 'mail'],
    "data": [
        "security/ir.model.access.csv",
    ],
    "application": False,
    "installable": True,
}
