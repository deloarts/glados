"""
The reduced user view. Every signed-in user reads the directory (id,
username, name, active state, account kind, avatar flag); the full view
with e-mail, permissions, groups, 2FA state and the last login needs
read:settings, except for one's own account. A user embedded in another
resource carries no e-mail either.
"""

from src.bootstrap.main import app
from src.modules.platform.domain.value_objects.permission import Permission

USERS = "/api/v1/web/users"
_HIDDEN = {
    "email",
    "permissions",
    "direct_permissions",
    "group_ids",
    "member_ids",
    "totp_enabled",
    "last_logged_in",
}


async def test_a_plain_user_cannot_read_the_full_list(auth_client) -> None:
    plain = await auth_client(username="plain", email="plain@example.com")

    assert (await plain.get(f"{USERS}/")).status_code == 403


async def test_a_plain_user_cannot_read_someone_elses_details(auth_client, create_user) -> None:
    other = await create_user(username="other", email="other@example.com")
    plain = await auth_client(username="plain", email="plain@example.com")

    assert (await plain.get(f"{USERS}/{other.id}")).status_code == 403


async def test_a_plain_user_reads_their_own_details(auth_client) -> None:
    plain = await auth_client(username="plain", email="plain@example.com")
    me = (await plain.get(f"{USERS}/me")).json()

    response = await plain.get(f"{USERS}/{me['id']}")

    assert response.status_code == 200
    assert response.json()["email"] == "plain@example.com"


async def test_user_administration_reads_the_full_view(auth_client, create_user) -> None:
    other = await create_user(username="other", email="other@example.com")
    admin = await auth_client(permissions=[Permission.READ_SETTINGS])

    response = await admin.get(f"{USERS}/{other.id}")

    assert response.status_code == 200
    assert response.json()["email"] == "other@example.com"


async def test_the_directory_carries_no_sensitive_field(auth_client, create_user) -> None:
    await create_user(username="other", email="other@example.com")
    plain = await auth_client(username="plain", email="plain@example.com")

    response = await plain.get(f"{USERS}/directory")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 2
    for item in body["items"]:
        assert _HIDDEN.isdisjoint(item), item
        assert {"id", "username", "full_name", "is_active", "has_avatar"} <= set(item)


async def test_the_directory_search_does_not_match_email(auth_client, create_user) -> None:
    await create_user(username="otherperson", email="secret@hidden.test")
    plain = await auth_client(username="plain", email="plain@example.com")

    by_mail = (await plain.get(f"{USERS}/directory", params={"search": "hidden.test"})).json()
    by_name = (await plain.get(f"{USERS}/directory", params={"search": "otherperson"})).json()

    assert by_mail["total"] == 0
    assert by_name["total"] == 1


async def test_the_directory_refuses_to_sort_by_email(auth_client) -> None:
    plain = await auth_client(username="plain", email="plain@example.com")

    response = await plain.get(f"{USERS}/directory", params={"order_by": "email"})

    assert response.status_code == 422


def test_an_embedded_user_carries_no_email() -> None:
    schemas = app.openapi()["components"]["schemas"]

    assert "email" not in schemas["PublicUserResponse"]["properties"]
    assert _HIDDEN.isdisjoint(schemas["UserSummaryResponse"]["properties"])
