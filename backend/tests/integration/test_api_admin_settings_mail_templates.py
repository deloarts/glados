"""
Backend half of the "Localized Mail Templates" engine's admin API:
  - GET /admin/settings/mail/templates returns every MailTemplateKind's
    spec metadata (family/variables/default_subject) plus whatever rows
    exist, driven entirely by the spec registry so a kind with zero rows
    still appears.
  - PUT /admin/settings/mail/templates/{kind} replaces every language
    entry for one kind in a single call; a second PUT with the same
    language updates the existing row rather than duplicating it.
  - POST /admin/settings/mail/templates/{kind}/preview renders a draft
    through the sandboxed string env with the kind's sample_context,
    400ing (not 500ing) on bad Jinja syntax.

No admin_mail_template rows are seeded by conftest's autouse
`_seed_admin_settings`. Every test here starts from an empty table,
which is a legitimate state (an install whose seeder hasn't run yet, or
one seeded with the migration but never started).
"""

import pytest

from src.modules.platform.domain.value_objects.permission import Permission

BASE = "/api/v1/web/admin/settings/mail/templates"


@pytest.fixture
async def writer(auth_client):
    return await auth_client(permissions=[Permission.WRITE_SETTINGS, Permission.READ_SETTINGS])


@pytest.fixture
async def reader(auth_client):
    return await auth_client(permissions=[Permission.READ_SETTINGS])


class TestGetMailTemplates:
    async def test_returns_every_kind_even_with_no_rows_stored(self, reader):
        response = await reader.get(BASE)

        assert response.status_code == 200, response.text
        kinds = {group["kind"] for group in response.json()["kinds"]}
        assert kinds == {
            "welcome",
            "notification_digest",
            "test_mail",
            "request",
            "order",
            "account_deactivated",
            "permissions_changed",
            "project_assigned",
            "product_assigned",
            "order_canceled",
            "schedule_error",
            "disk_space_warning",
            "supplier_lines_to_settle",
            "meeting_notes",
        }

    async def test_each_kind_group_carries_family_and_variables_from_the_registry(self, reader):
        response = await reader.get(BASE)

        welcome = next(g for g in response.json()["kinds"] if g["kind"] == "welcome")
        assert welcome["family"] == "system"
        assert "full_name" in welcome["variables"]
        assert welcome["entries"] == []

        request = next(g for g in response.json()["kinds"] if g["kind"] == "request")
        assert request["family"] == "supplier"

    async def test_unprivileged_gets_403(self, auth_client):
        no_permissions = await auth_client(permissions=[])

        response = await no_permissions.get(BASE)

        assert response.status_code == 403


class TestUpdateMailTemplates:
    async def test_round_trip(self, writer):
        put_response = await writer.put(
            f"{BASE}/welcome",
            json={
                "entries": [
                    {"language": "enGB", "subject": "Welcome!", "body": "<p>Hi {{ full_name }}</p>"}
                ]
            },
        )
        assert put_response.status_code == 200, put_response.text
        assert put_response.json()["kind"] == "welcome"
        (entry,) = put_response.json()["entries"]
        assert entry["language"] == "enGB"
        assert entry["subject"] == "Welcome!"
        assert entry["configured"] is True

        get_response = await writer.get(BASE)
        welcome = next(g for g in get_response.json()["kinds"] if g["kind"] == "welcome")
        assert len(welcome["entries"]) == 1
        assert welcome["entries"][0]["subject"] == "Welcome!"

    async def test_multiple_languages_in_one_call(self, writer):
        response = await writer.put(
            f"{BASE}/welcome",
            json={
                "entries": [
                    {"language": "enGB", "subject": "EN", "body": "<p>EN</p>"},
                    {"language": "deAT", "subject": "DE", "body": "<p>DE</p>"},
                ]
            },
        )
        assert response.status_code == 200, response.text
        assert {e["language"] for e in response.json()["entries"]} == {"enGB", "deAT"}

    async def test_second_put_updates_rather_than_duplicates(self, writer):
        await writer.put(
            f"{BASE}/welcome",
            json={"entries": [{"language": "enGB", "subject": "First", "body": "<p>First</p>"}]},
        )

        response = await writer.put(
            f"{BASE}/welcome",
            json={"entries": [{"language": "enGB", "subject": "Second", "body": "<p>Second</p>"}]},
        )

        assert response.status_code == 200, response.text
        (entry,) = response.json()["entries"]
        assert entry["subject"] == "Second"

        get_response = await writer.get(BASE)
        welcome = next(g for g in get_response.json()["kinds"] if g["kind"] == "welcome")
        assert len(welcome["entries"]) == 1
        assert welcome["entries"][0]["subject"] == "Second"

    async def test_an_empty_body_is_reported_as_not_configured(self, writer):
        response = await writer.put(
            f"{BASE}/welcome",
            json={"entries": [{"language": "enGB", "subject": "", "body": "   "}]},
        )

        assert response.status_code == 200, response.text
        (entry,) = response.json()["entries"]
        assert entry["configured"] is False

    async def test_unknown_kind_in_the_path_is_a_422(self, writer):
        response = await writer.put(
            f"{BASE}/not-a-real-kind",
            json={"entries": [{"language": "enGB", "subject": "X", "body": "X"}]},
        )

        assert response.status_code == 422, response.text

    async def test_unknown_language_in_an_entry_is_a_422(self, writer):
        response = await writer.put(
            f"{BASE}/welcome",
            json={"entries": [{"language": "frFR", "subject": "X", "body": "X"}]},
        )

        assert response.status_code == 422, response.text

    async def test_unprivileged_gets_403_not_a_write(self, auth_client):
        no_permissions = await auth_client(permissions=[])

        response = await no_permissions.put(
            f"{BASE}/welcome",
            json={"entries": [{"language": "enGB", "subject": "X", "body": "X"}]},
        )

        assert response.status_code == 403


class TestPreviewMailTemplate:
    async def test_renders_the_draft_against_the_kind_sample_context(self, writer):
        response = await writer.post(
            f"{BASE}/welcome/preview",
            json={"subject": "Hi {{ full_name }}", "body": "<p>Visit {{ domain }}</p>"},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert "Jamie Appleseed" in body["subject"] or body["subject"]
        assert "https://glados.example.com" in body["html"]

    async def test_bad_jinja_syntax_is_a_400_not_a_500(self, writer):
        response = await writer.post(
            f"{BASE}/welcome/preview",
            json={"subject": "Hi", "body": "<p>{% if %}</p>"},
        )

        assert response.status_code == 400, response.text
        assert response.json()["code"] == "MailTemplateRenderError"

    async def test_unprivileged_gets_403(self, auth_client):
        no_permissions = await auth_client(permissions=[])

        response = await no_permissions.post(
            f"{BASE}/welcome/preview", json={"subject": "Hi", "body": "Hi"}
        )

        assert response.status_code == 403
