"""
Unit tests for the pure functions in
src/modules/platform/domain/services/mail_template_resolution.py: the §1 fallback chain
(recipient language -> tenant default -> enGB -> packaged file) minus the
packaged-file floor, which lives in the caller (smtp_mail_service._render,
covered separately in test_smtp_mail_service.py).
"""

from src.modules.platform.domain.entities.admin_settings.mail import AdminMailTemplate
from src.modules.platform.domain.services.mail_template_resolution import language_preference_order
from src.modules.platform.domain.services.mail_template_resolution import pick_template
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.mail_template_kind import MailTemplateKind

WELCOME = MailTemplateKind.WELCOME
DE = Language.deAT
EN = Language.enGB


def _template(
    kind: MailTemplateKind, language: Language, body: str = "<p>Hi</p>"
) -> AdminMailTemplate:
    return AdminMailTemplate(id=1, kind=kind, language=language, subject="Subject", body=body)


# ── language_preference_order ────────────────────────────────────────


class TestLanguagePreferenceOrder:
    def test_requested_then_tenant_default_then_engb(self):
        assert language_preference_order(DE, EN) == [DE, EN]
        assert language_preference_order(EN, DE) == [EN, DE]

    def test_missing_ones_are_dropped(self):
        assert language_preference_order(None, None) == [EN]

    def test_duplicates_are_removed_keeping_first_occurrence(self):
        """A tenant whose default already is enGB must not list it twice,
        and a requested language equal to the tenant default collapses to
        one entry."""
        assert language_preference_order(EN, EN) == [EN]
        assert language_preference_order(DE, DE) == [DE, EN]

    def test_the_tenant_default_alone_still_ends_on_engb(self):
        assert language_preference_order(None, DE) == [DE, EN]

    def test_requested_only(self):
        assert language_preference_order(DE, None) == [DE, EN]


# ── pick_template ─────────────────────────────────────────────────────


class TestPickTemplate:
    def test_first_non_blank_body_in_language_order_wins(self):
        templates = [
            _template(WELCOME, EN, body="<p>EN</p>"),
            _template(WELCOME, DE, body="<p>DE</p>"),
        ]
        picked = pick_template(templates, WELCOME, [DE, EN])
        assert picked is not None
        assert picked.language is DE

    def test_a_blank_body_is_treated_as_absent(self):
        """A newly added language seeds empty (InitDatabase), never a copy
        of another language, so a blank row must fall through exactly like
        a missing one."""
        templates = [
            _template(WELCOME, DE, body=""),
            _template(WELCOME, EN, body="<p>EN</p>"),
        ]
        picked = pick_template(templates, WELCOME, [DE, EN])
        assert picked is not None
        assert picked.language is EN

    def test_a_whitespace_only_body_is_also_treated_as_absent(self):
        templates = [_template(WELCOME, DE, body="   \n  ")]
        assert pick_template(templates, WELCOME, [DE, EN]) is None

    def test_none_when_nothing_configured_anywhere(self):
        assert pick_template([], WELCOME, [DE, EN]) is None

    def test_only_matches_the_requested_kind(self):
        templates = [_template(MailTemplateKind.NOTIFICATION_DIGEST, EN, body="<p>Digest</p>")]
        assert pick_template(templates, WELCOME, [EN]) is None

    def test_default_language_is_enGB(self):
        """Sanity check tying this module's assumptions to the actual
        Language enum default, so a future change to that default fails
        loudly here rather than silently changing the floor everywhere."""
        assert Language.default() == Language.enGB
