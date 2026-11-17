"""
Backend half of GET /mail/templates/default: the order composer's fallback
to the tenant-wide admin default template when a supplier has none of its
own (see GetDefaultMailTemplate / ResolvedMailTemplateResult).

Authenticated only, deliberately no permission gate: every ordinary user
composing a supplier mail needs this, not just an admin, see the endpoint's
own docstring. `kind` is a Literal of the three SUPPLIER-family kinds, not
MailTemplateKind, so a SYSTEM-family body (e.g. `welcome`) can never reach
a non-admin through it. That is enforced at the wire boundary as a 422,
not inside the use case.
"""

import pytest

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.platform.domain.entities.admin_settings.mail import AdminMailTemplate
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.mail_template_kind import MailTemplateKind

BASE = "/api/v1/web/mail/templates/default"


async def _seed_template(
    db, kind: MailTemplateKind, language: Language, subject: str, body: str
) -> None:
    await SqlAlchemyAdminSettingsRepository(db).save_mail_template(
        AdminMailTemplate(id=0, kind=kind, language=language, subject=subject, body=body)
    )
    await db.commit()


@pytest.fixture
async def no_permissions(auth_client):
    """No read:settings/write:settings at all: this endpoint must still
    answer, unlike the admin templates API."""
    return await auth_client(permissions=[])


class TestNoPermissionGate:
    async def test_a_user_with_no_settings_permissions_gets_200(self, no_permissions):
        response = await no_permissions.get(BASE, params={"kind": "order"})

        assert response.status_code == 200, response.text


class TestSystemKindIsRejected:
    async def test_a_system_family_kind_is_a_422_not_a_200(self, no_permissions):
        """`welcome` is SYSTEM-family and must never reach a non-admin
        through this endpoint. The Literal type rejects it before the
        use case ever runs."""
        response = await no_permissions.get(BASE, params={"kind": "welcome"})

        assert response.status_code == 422, response.text

    async def test_an_unrelated_string_is_also_a_422(self, no_permissions):
        response = await no_permissions.get(BASE, params={"kind": "not-a-kind"})

        assert response.status_code == 422, response.text


class TestNothingConfigured:
    async def test_configured_is_false_with_no_rows_at_all(self, no_permissions):
        response = await no_permissions.get(BASE, params={"kind": "order"})

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["configured"] is False
        assert body["subject"] == ""
        assert body["body"] == ""


class TestFallbackChain:
    async def test_the_requested_language_wins_when_configured(self, no_permissions, db):
        await _seed_template(db, MailTemplateKind.ORDER, Language.deAT, "DE Subject", "<p>DE</p>")
        await _seed_template(db, MailTemplateKind.ORDER, Language.enGB, "EN Subject", "<p>EN</p>")

        response = await no_permissions.get(BASE, params={"kind": "order", "language": "deAT"})

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["configured"] is True
        assert body["language"] == "deAT"
        assert body["body"] == "<p>DE</p>"

    async def test_an_unconfigured_requested_language_falls_back_to_engb(self, no_permissions, db):
        await _seed_template(db, MailTemplateKind.ORDER, Language.enGB, "EN Subject", "<p>EN</p>")

        response = await no_permissions.get(BASE, params={"kind": "order", "language": "deAT"})

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["configured"] is True
        assert body["language"] == "enGB"
        assert body["body"] == "<p>EN</p>"

    async def test_an_unknown_requested_language_falls_back_to_engb(self, no_permissions, db):
        """The query parameter is free text, so a language no member names
        drops out of the chain instead of failing the request."""
        await _seed_template(db, MailTemplateKind.ORDER, Language.enGB, "EN Subject", "<p>EN</p>")

        response = await no_permissions.get(BASE, params={"kind": "order", "language": "frFR"})

        assert response.status_code == 200, response.text
        assert response.json()["language"] == "enGB"

    async def test_no_requested_language_uses_the_tenant_default(self, no_permissions, db):
        """conftest's autouse _seed_admin_settings seeds admin_general_
        settings without default_language, so the tenant default is the
        server_default, enGB (src.modules.platform.const.SERVER_DEFAULT_LANGUAGE)."""
        await _seed_template(db, MailTemplateKind.ORDER, Language.enGB, "EN Subject", "<p>EN</p>")

        response = await no_permissions.get(BASE, params={"kind": "order"})

        assert response.status_code == 200, response.text
        assert response.json()["language"] == "enGB"

    async def test_order_canceled_is_a_valid_kind(self, no_permissions, db):
        await _seed_template(
            db, MailTemplateKind.ORDER_CANCELED, Language.enGB, "Canceled", "<p>Canceled</p>"
        )

        response = await no_permissions.get(BASE, params={"kind": "order_canceled"})

        assert response.status_code == 200, response.text
        assert response.json()["configured"] is True
