# -*- coding: utf-8 -*-
"""Migrate rp.tender.package state values.

P5.1 reshapes state machine: draft → approved → inviting → ... → closed.
Old states 'active' was a single 'in progress' bucket — map to 'approved'
(an active package that hasn't started bidding yet is the conservative
default).

'draft' and 'closed' keep same key — no UPDATE needed.
"""


def migrate(cr, version):
    cr.execute(
        "UPDATE rp_tender_package SET state = 'approved' "
        "WHERE state = 'active'"
    )
