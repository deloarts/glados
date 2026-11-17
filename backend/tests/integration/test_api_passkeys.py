"""
Passkeys end to end, with a software authenticator answering the options
the backend hands out, so py_webauthn verifies real signatures: registering
behind a confirmed password, the passkey login skipping TOTP, challenge
replay, the refusals, and the self-service and administrative removal.
"""

from urllib.parse import urlsplit

import httpx
import pytest

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.domain.entities.admin_settings.auth import AdminAuthSettings
from src.modules.platform.domain.entities.admin_settings.security import AdminSecuritySettings
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.config.settings import cfg
from src.modules.platform.infrastructure.security.totp import generate_totp_secret
from tests.factories import TEST_PASSWORD
from tests.soft_authenticator import SoftAuthenticator
from tests.soft_authenticator import b64url

from .conftest import _new_client
from .conftest import auth_headers

MY_PASSKEYS = "/api/v1/web/users/me/passkeys/"
LOGIN_OPTIONS = "/api/v1/auth/login/passkey/options"
LOGIN = "/api/v1/auth/login/passkey"


@pytest.fixture(autouse=True)
async def _seed_login_settings(db) -> None:
    """The security and auth singletons the password confirmation reads."""
    repo = SqlAlchemyAdminSettingsRepository(db)
    await repo.save_security(
        AdminSecuritySettings(
            id=1,
            enforce_totp=False,
            allow_rfid_login=True,
            allow_local_login=True,
            enable_api_key_auth=False,
            min_password_length=8,
            session_timeout_minutes=0,
            totp_trusted_device_days=0,
            max_login_attempts=5,
            lockout_duration_minutes=15,
            token_max_lifetime_days=3650,
        )
    )
    await repo.save_auth(
        AdminAuthSettings(
            id=1,
            ldap_enabled=False,
            ldap_host="",
            ldap_port=636,
            ldap_use_ssl=True,
            ldap_start_tls=False,
            ldap_verify_certificate=True,
            ldap_domain="",
            ldap_timeout_seconds=5,
        )
    )
    await db.commit()


_ORIGIN = "{0.scheme}://{0.netloc}".format(urlsplit(cfg.domain))
_RP_ID = urlsplit(cfg.domain).hostname or "localhost"


async def _register(
    client: httpx.AsyncClient, authenticator: SoftAuthenticator, name: str = "Office PC"
) -> httpx.Response:
    begin = await client.post(
        f"{MY_PASSKEYS}registration-options", json={"password": TEST_PASSWORD}
    )
    assert begin.status_code == 200, begin.text
    body = begin.json()
    return await client.post(
        MY_PASSKEYS,
        json={
            "challenge_token": body["challenge_token"],
            "credential": authenticator.create(body["options"]),
            "name": name,
        },
    )


async def _login(client: httpx.AsyncClient, authenticator: SoftAuthenticator) -> httpx.Response:
    options = (await client.post(LOGIN_OPTIONS)).json()
    return await client.post(
        LOGIN,
        json={
            "challenge_token": options["challenge_token"],
            "credential": authenticator.get(options["options"], rp_id=_RP_ID),
        },
    )


async def test_register_list_and_sign_in_with_a_passkey(auth_client, client) -> None:
    me = await auth_client()
    authenticator = SoftAuthenticator(_ORIGIN)

    created = await _register(me, authenticator)
    assert created.status_code == 201, created.text
    assert created.json()["name"] == "Office PC"

    listed = await me.get(MY_PASSKEYS)
    assert [p["name"] for p in listed.json()] == ["Office PC"]

    login = await _login(client, authenticator)
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    check = await client.post(
        "/api/v1/auth/login/test-token", headers={"Authorization": f"Bearer {token}"}
    )
    assert check.status_code == 200

    after = (await me.get(MY_PASSKEYS)).json()[0]
    assert after["last_used_at"] is not None


async def test_registration_options_exclude_existing_passkeys(auth_client) -> None:
    me = await auth_client()
    authenticator = SoftAuthenticator(_ORIGIN)
    assert (await _register(me, authenticator)).status_code == 201

    begin = await me.post(f"{MY_PASSKEYS}registration-options", json={"password": TEST_PASSWORD})
    excluded = begin.json()["options"]["excludeCredentials"]
    assert [c["id"] for c in excluded] == [b64url(authenticator.credential_id)]


async def test_wrong_password_is_refused_and_counted(auth_client, login_attempts) -> None:
    me = await auth_client()
    resp = await me.post(f"{MY_PASSKEYS}registration-options", json={"password": "wrong"})
    assert resp.status_code == 400
    assert resp.json()["code"] == "PasswordConfirmationFailedError"
    assert login_attempts.failures["tester"] == 1
    assert login_attempts.failures["tester|testclient"] == 1


async def test_registration_without_user_verification_is_refused(auth_client) -> None:
    me = await auth_client()
    resp = await _register(me, SoftAuthenticator(_ORIGIN, user_verified=False))
    assert resp.status_code == 400
    assert resp.json()["code"] == "PasskeyRegistrationFailedError"
    assert (await me.get(MY_PASSKEYS)).json() == []


async def test_registration_from_another_origin_is_refused(auth_client) -> None:
    me = await auth_client()
    resp = await _register(me, SoftAuthenticator("https://evil.example.com"))
    assert resp.status_code == 400
    assert resp.json()["code"] == "PasskeyRegistrationFailedError"


async def test_registration_challenge_cannot_be_redeemed_twice(auth_client) -> None:
    me = await auth_client()
    begin = (
        await me.post(f"{MY_PASSKEYS}registration-options", json={"password": TEST_PASSWORD})
    ).json()
    first = SoftAuthenticator(_ORIGIN)
    ok = await me.post(
        MY_PASSKEYS,
        json={
            "challenge_token": begin["challenge_token"],
            "credential": first.create(begin["options"]),
        },
    )
    assert ok.status_code == 201
    again = await me.post(
        MY_PASSKEYS,
        json={
            "challenge_token": begin["challenge_token"],
            "credential": SoftAuthenticator(_ORIGIN).create(begin["options"]),
        },
    )
    assert again.status_code == 400
    assert again.json()["code"] == "PasskeyRegistrationFailedError"


async def test_registration_token_of_another_user_is_refused(auth_client) -> None:
    alice = await auth_client(username="alice", email="alice@example.com")
    bob = await auth_client(username="bob", email="bob@example.com")
    begin = (
        await alice.post(f"{MY_PASSKEYS}registration-options", json={"password": TEST_PASSWORD})
    ).json()
    resp = await bob.post(
        MY_PASSKEYS,
        json={
            "challenge_token": begin["challenge_token"],
            "credential": SoftAuthenticator(_ORIGIN).create(begin["options"]),
        },
    )
    assert resp.status_code == 400


async def test_system_user_cannot_register(auth_client) -> None:
    system = await auth_client(username="sysadmin", email="sys@example.com", is_systemuser=True)
    resp = await system.post(f"{MY_PASSKEYS}registration-options", json={"password": TEST_PASSWORD})
    assert resp.status_code == 403


async def test_passkey_login_skips_totp(auth_client, client, db) -> None:
    me = await auth_client()
    authenticator = SoftAuthenticator(_ORIGIN)
    assert (await _register(me, authenticator)).status_code == 201

    repo = SqlAlchemyUserRepository(db)
    user = await repo.get_by_username_or_email("tester")
    assert user is not None
    user.totp_secret = generate_totp_secret()
    user.totp_enabled = True
    await repo.save(user)
    await db.commit()

    login = await _login(client, authenticator)
    assert login.status_code == 200, login.text
    assert "access_token" in login.json()


async def test_login_challenge_cannot_be_replayed(auth_client, client) -> None:
    me = await auth_client()
    authenticator = SoftAuthenticator(_ORIGIN)
    assert (await _register(me, authenticator)).status_code == 201

    options = (await client.post(LOGIN_OPTIONS)).json()
    body = {
        "challenge_token": options["challenge_token"],
        "credential": authenticator.get(options["options"], rp_id=_RP_ID),
    }
    assert (await client.post(LOGIN, json=body)).status_code == 200
    replay = await client.post(LOGIN, json=body)
    assert replay.status_code == 401
    assert replay.json()["code"] == "PasskeyRejectedError"


async def test_unknown_passkey_is_rejected(client) -> None:
    authenticator = SoftAuthenticator(_ORIGIN)
    authenticator.create({"user": {"id": "AAAA"}, "rp": {"id": _RP_ID}, "challenge": "AAAA"})
    resp = await _login(client, authenticator)
    assert resp.status_code == 401
    assert resp.json()["code"] == "PasskeyRejectedError"


async def test_inactive_user_cannot_sign_in(auth_client, client, db) -> None:
    me = await auth_client()
    authenticator = SoftAuthenticator(_ORIGIN)
    assert (await _register(me, authenticator)).status_code == 201

    repo = SqlAlchemyUserRepository(db)
    user = await repo.get_by_username_or_email("tester")
    assert user is not None
    user.is_active = False
    await repo.save(user)
    await db.commit()

    resp = await _login(client, authenticator)
    assert resp.status_code == 403
    assert resp.json()["code"] == "InactiveUserError"


async def test_delete_own_passkey(auth_client, client) -> None:
    me = await auth_client()
    authenticator = SoftAuthenticator(_ORIGIN)
    public_id = (await _register(me, authenticator)).json()["public_id"]

    assert (await me.delete(f"{MY_PASSKEYS}{public_id}")).status_code == 204
    assert (await me.delete(f"{MY_PASSKEYS}{public_id}")).status_code == 404
    assert (await _login(client, authenticator)).status_code == 401


async def test_admin_lists_and_removes_another_users_passkeys(
    auth_client, create_user, client
) -> None:
    target = await create_user(username="worker", email="worker@example.com")
    worker = _new_client()
    worker.headers.update(await auth_headers(target))
    authenticator = SoftAuthenticator(_ORIGIN)
    assert (await _register(worker, authenticator)).status_code == 201

    admin = await auth_client(
        [Permission.WRITE_SETTINGS], username="admin", email="admin@example.com"
    )
    listed = await admin.get(f"/api/v1/web/users/{target.id}/passkeys")
    assert len(listed.json()) == 1

    reset = await admin.delete(f"/api/v1/web/users/{target.id}/passkeys")
    assert reset.status_code == 200
    assert reset.json() == {"revoked": 1}
    assert (await _login(client, authenticator)).status_code == 401
    await worker.aclose()


async def test_reset_needs_write_settings_and_another_user(
    auth_client, create_user, client
) -> None:
    target = await create_user(username="worker", email="worker@example.com")
    plain = await auth_client(username="plain", email="plain@example.com")
    assert (await plain.delete(f"/api/v1/web/users/{target.id}/passkeys")).status_code == 403

    admin = await create_user(
        username="admin", email="admin@example.com", permissions=[Permission.WRITE_SETTINGS]
    )
    own = await client.delete(
        f"/api/v1/web/users/{admin.id}/passkeys", headers=await auth_headers(admin)
    )
    assert own.status_code == 403


async def test_without_write_settings_a_missing_user_is_refused_not_unknown(auth_client) -> None:
    plain = await auth_client(username="plain", email="plain@example.com")

    assert (await plain.get("/api/v1/web/users/9999/passkeys")).status_code == 403
    assert (await plain.delete("/api/v1/web/users/9999/passkeys")).status_code == 403


async def test_login_options_name_no_credentials(client) -> None:
    options = (await client.post(LOGIN_OPTIONS)).json()["options"]
    assert options.get("allowCredentials", []) == []
    assert options["userVerification"] == "required"


async def test_delete_all_own_passkeys(auth_client, client) -> None:
    me = await auth_client()
    first, second = SoftAuthenticator(_ORIGIN), SoftAuthenticator(_ORIGIN)
    assert (await _register(me, first)).status_code == 201
    assert (await _register(me, second, name="Laptop")).status_code == 201

    resp = await me.delete(MY_PASSKEYS)
    assert resp.json() == {"revoked": 2}
    assert (await me.get(MY_PASSKEYS)).json() == []
    assert (await _login(client, first)).status_code == 401


async def test_rename_own_passkey(auth_client) -> None:
    me = await auth_client()
    public_id = (await _register(me, SoftAuthenticator(_ORIGIN))).json()["public_id"]

    resp = await me.patch(f"{MY_PASSKEYS}{public_id}", json={"name": "  Laptop  "})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Laptop"
    assert [p["name"] for p in (await me.get(MY_PASSKEYS)).json()] == ["Laptop"]


async def test_rename_refuses_a_blank_name(auth_client) -> None:
    me = await auth_client()
    public_id = (await _register(me, SoftAuthenticator(_ORIGIN))).json()["public_id"]

    assert (await me.patch(f"{MY_PASSKEYS}{public_id}", json={"name": "   "})).status_code == 422


async def test_rename_another_users_passkey_is_not_found(auth_client) -> None:
    alice = await auth_client(username="alice", email="alice@example.com")
    bob = await auth_client(username="bob", email="bob@example.com")
    public_id = (await _register(alice, SoftAuthenticator(_ORIGIN))).json()["public_id"]

    resp = await bob.patch(f"{MY_PASSKEYS}{public_id}", json={"name": "Mine now"})
    assert resp.status_code == 404
