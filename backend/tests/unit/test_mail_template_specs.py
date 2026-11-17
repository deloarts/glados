"""
Pins the completeness invariants MAIL_TEMPLATE_SPECS must hold for the rest
of the engine (seeder, resolver, API, editor chips) to trust it blindly:
every MailTemplateKind has an entry, and every entry's sample_context
actually covers the variables it declares. PreviewMailTemplate renders
`**sample_context` straight into the template, so a declared variable
missing from the sample would either KeyError or (for a plain `{{ var }}`
reference under Jinja's default Undefined) silently render empty instead
of a real sample value.
"""

from src.modules.platform.domain.services.mail_template_specs import MAIL_TEMPLATE_SPECS
from src.modules.platform.domain.services.mail_template_specs import MailTemplateFamily
from src.modules.platform.domain.value_objects.mail_template_kind import MailTemplateKind


class TestSpecCompleteness:
    def test_every_kind_has_a_spec(self):
        assert set(MAIL_TEMPLATE_SPECS.keys()) == set(MailTemplateKind)

    def test_every_spec_is_keyed_by_its_own_kind(self):
        for kind, spec in MAIL_TEMPLATE_SPECS.items():
            assert spec.kind == kind

    def test_every_spec_declares_a_family(self):
        for spec in MAIL_TEMPLATE_SPECS.values():
            assert spec.family in (MailTemplateFamily.SYSTEM, MailTemplateFamily.SUPPLIER)

    def test_every_spec_sample_context_covers_its_declared_variables(self):
        for kind, spec in MAIL_TEMPLATE_SPECS.items():
            missing = [v for v in spec.variables if v not in spec.sample_context]
            assert not missing, f"{kind}: sample_context missing {missing}"

    def test_every_spec_has_a_non_empty_default_subject(self):
        for kind, spec in MAIL_TEMPLATE_SPECS.items():
            assert spec.default_subject.strip(), f"{kind}: default_subject is blank"

    def test_variables_are_declared_as_a_tuple(self):
        """Not a list: the dataclass is frozen (hashable value semantics),
        and a tuple is what the API/editor iterate over as a stable,
        ordered chip list."""
        for spec in MAIL_TEMPLATE_SPECS.values():
            assert isinstance(spec.variables, tuple)


class TestPhaseOneKindsAreSystemOrSupplier:
    def test_welcome_notification_digest_test_mail_are_system(self):
        for kind in (
            MailTemplateKind.WELCOME,
            MailTemplateKind.NOTIFICATION_DIGEST,
            MailTemplateKind.TEST_MAIL,
        ):
            assert MAIL_TEMPLATE_SPECS[kind].family == MailTemplateFamily.SYSTEM

    def test_request_and_order_are_supplier_and_share_variables(self):
        request = MAIL_TEMPLATE_SPECS[MailTemplateKind.REQUEST]
        order = MAIL_TEMPLATE_SPECS[MailTemplateKind.ORDER]
        assert request.family == MailTemplateFamily.SUPPLIER
        assert order.family == MailTemplateFamily.SUPPLIER
        assert request.variables == order.variables
