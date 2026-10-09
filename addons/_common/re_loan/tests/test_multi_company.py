# -*- coding: utf-8 -*-
"""
Tests for multi-company isolation via ir.rule on the loan models.

Each loan model carries a `company_id` and is filtered by a global
ir.rule (`('company_id', 'in', company_ids)`). These tests verify that
a user scoped to Company A cannot see, write, or delete Company B's
data, and that the ALLOWED COMPANIES switcher correctly broadens the
view when a user has access to multiple companies.
"""
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 're_loan', 're_loan_security')
class TestLoanMultiCompanyIsolation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Company = cls.env['res.company']
        Users = cls.env['res.users']
        Partner = cls.env['res.partner']
        loan_user_grp = cls.env.ref('re_loan.group_loan_user')

        # Two distinct companies, each with its own bank counterparty.
        cls.company_a = Company.create({'name': 'CĐT Anpha'})
        cls.company_b = Company.create({'name': 'CĐT Beta'})

        cls.bank = Partner.create({
            'name': 'Ngân hàng BIDV',
            'is_company': True,
            'is_bank': True,
        })

        # Users: each scoped to a SINGLE company. Both belong to the
        # loan-user group so we're testing the multi-company rule, not
        # the ACL.
        cls.user_a = Users.create({
            'name': 'Loan User A',
            'login': 'loan_user_a@test.local',
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
            'group_ids': [(4, loan_user_grp.id)],
        })
        cls.user_b = Users.create({
            'name': 'Loan User B',
            'login': 'loan_user_b@test.local',
            'company_id': cls.company_b.id,
            'company_ids': [(6, 0, [cls.company_b.id])],
            'group_ids': [(4, loan_user_grp.id)],
        })

        # Cross-company manager (sees BOTH) — proves the rule respects
        # the allowed_company_ids set, not a hard-pinned company_id.
        cls.user_both = Users.create({
            'name': 'Loan Manager (multi-co)',
            'login': 'loan_mgr_multi@test.local',
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id, cls.company_b.id])],
            'group_ids': [(4, loan_user_grp.id)],
        })

        # One contract per company. Use sudo() with explicit company so
        # we don't need User A's session to seed Company A's data.
        Contract = cls.env['re.loan.credit.contract']
        cls.contract_a = Contract.with_company(cls.company_a).create({
            'name': 'HĐTD-A-01/2026',
            'partner_id': cls.bank.id,
            'amount_total': 100_000_000_000.0,
            'company_id': cls.company_a.id,
        })
        cls.contract_b = Contract.with_company(cls.company_b).create({
            'name': 'HĐTD-B-01/2026',
            'partner_id': cls.bank.id,
            'amount_total': 200_000_000_000.0,
            'company_id': cls.company_b.id,
        })

    # ----- Read isolation -------------------------------------------------
    def test_user_a_sees_only_company_a_contract(self):
        contracts = self.env['re.loan.credit.contract'] \
            .with_user(self.user_a).search([])
        self.assertIn(self.contract_a, contracts)
        self.assertNotIn(self.contract_b, contracts)

    def test_user_b_sees_only_company_b_contract(self):
        contracts = self.env['re.loan.credit.contract'] \
            .with_user(self.user_b).search([])
        self.assertIn(self.contract_b, contracts)
        self.assertNotIn(self.contract_a, contracts)

    def test_multi_company_user_sees_both(self):
        contracts = self.env['re.loan.credit.contract'] \
            .with_user(self.user_both).search([])
        self.assertIn(self.contract_a, contracts)
        self.assertIn(self.contract_b, contracts)

    # ----- Direct browse blocked too --------------------------------------
    def test_user_a_cannot_read_company_b_contract_directly(self):
        # Even a direct browse() of the foreign id is filtered: read()
        # raises AccessError when the record is outside the rule scope.
        foreign = self.contract_b.with_user(self.user_a)
        with self.assertRaises(AccessError):
            foreign.read(['name'])

    # ----- Write isolation ------------------------------------------------
    def test_user_a_cannot_write_company_b_contract(self):
        with self.assertRaises(AccessError):
            self.contract_b.with_user(self.user_a).write({
                'name': 'Sabotage attempt',
            })

    # ----- Cross-model: facility inherits the same isolation --------------
    def test_facility_isolation(self):
        Facility = self.env['re.loan.facility']
        fac_a = Facility.with_company(self.company_a).create({
            'credit_contract_id': self.contract_a.id,
            'name': 'Facility A',
            'amount_limit': 50_000_000_000.0,
            'company_id': self.company_a.id,
        })
        fac_b = Facility.with_company(self.company_b).create({
            'credit_contract_id': self.contract_b.id,
            'name': 'Facility B',
            'amount_limit': 80_000_000_000.0,
            'company_id': self.company_b.id,
        })

        facs_for_a = Facility.with_user(self.user_a).search([])
        self.assertIn(fac_a, facs_for_a)
        self.assertNotIn(fac_b, facs_for_a)


@tagged('post_install', '-at_install', 're_loan', 're_loan_security')
class TestCompanyRuleCoverage(TransactionCase):
    """Không để sót model nào mang dữ liệu công ty mà thiếu luật.

    ACL chỉ nói ĐƯỢC ĐỌC MODEL NÀO, không nói ĐƯỢC ĐỌC DÒNG NÀO. Một
    model mang `company_id` mà thiếu ir.rule toàn cục là người dùng
    công ty A đọc được dữ liệu công ty B — kể cả quản lý nghiệp vụ,
    vì nhóm quản lý không vượt được ir.rule.

    Bài kiểm quét MỌI model của bộ Realty đang cài trong DB kiểm thử,
    nên thêm model mới mà quên luật là nổ ngay tại đây, không chờ ai
    phát hiện trên môi trường khách.
    """

    # Model cố ý KHÔNG có luật — kèm lý do. Thêm vào đây là một quyết
    # định, không phải cách làm cho bài kiểm im lặng.
    EXEMPT = {
        # Dữ liệu danh mục dùng chung mọi công ty.
        're.loan.collateral.type',
        're.loan.purpose',
    }

    def test_every_company_model_has_global_rule(self):
        IrModel = self.env['ir.model']
        Rule = self.env['ir.rule']
        missing = []
        for model_name in sorted(self.env.registry.keys()):
            model = self.env[model_name]
            # Transient: bản ghi riêng từng người dùng, Odoo tự dọn và
            # tự chặn. Abstract: không có bảng để lọc.
            if model._transient or model._abstract:
                continue
            if model_name in self.EXEMPT:
                continue
            rec = IrModel.search([('model', '=', model_name)], limit=1)
            modules = set((rec.modules or '').replace(' ', '').split(','))
            if not any(m.startswith(('re_', 'rp_')) for m in modules):
                continue
            field = model._fields.get('company_id')
            if not field:
                continue
            if not field.store:
                missing.append('%s (company_id KHÔNG lưu — luật không '
                               'lọc được bằng SQL)' % model_name)
                continue
            rules = Rule.sudo().search([
                ('model_id.model', '=', model_name),
                ('global', '=', True),
            ])
            if not any('company_id' in (r.domain_force or '')
                       for r in rules):
                missing.append('%s (thiếu ir.rule toàn cục)' % model_name)
        self.assertFalse(
            missing,
            'Model mang dữ liệu công ty nhưng không lọc theo công ty:\n  '
            + '\n  '.join(missing))
