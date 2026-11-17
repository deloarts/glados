"""
HTTP-level coverage of the API-key authentication surface. `key/router.py` applies
`Depends(get_current_api_key_user)` at the router level (unlike PAT, which
checks per-route), so one broken dependency breaks all 3 mounted routers at
once.

`get_current_api_key_user` also gates on the admin `enable_api_key_auth`
security toggle *before* it even looks at the credential (auth_deps.py),
default False, seeded True here via the real repository, same pattern
test_api_rfid_identify.py uses for its own security-settings row (the
autouse `_seed_admin_settings` fixture does not cover this domain).

Keys are minted through the real `CreateApiKey`/`RevokeApiKey` use cases
against the throwaway SQLite DB (`db` fixture), never a hand-built row.
"""

from collections.abc import Awaitable
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.api_key_repository import (
    SqlAlchemyApiKeyRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.application.dto.api_key_dto import CreateApiKeyCommand
from src.modules.platform.application.use_cases.api_key.create_api_key import CreateApiKey
from src.modules.platform.application.use_cases.api_key.revoke_api_key import RevokeApiKey
from src.modules.platform.domain.entities.admin_settings.security import AdminSecuritySettings
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.security.hashing import aget_hash
from src.modules.platform.infrastructure.security.rfid import rfid_lookup

# Every key router, and one route on it. Missing-credential-401 needs no
# seed data (the dependency raises before the route body runs at all), so
# a dummy path parameter is fine for the two id-based lookups.
_KEY_ROUTES = [
    ("GET", "/api/v1/key/products/1", None),
    ("GET", "/api/v1/key/projects/1", None),
    ("POST", "/api/v1/key/users/rfid", {"rfid": "00000000"}),
]
_RFID_LOOKUP = "/api/v1/key/users/rfid"


@pytest.fixture(autouse=True)
async def _enable_api_key_auth(db: Session) -> None:
    """`enable_api_key_auth` defaults False; every test in this file needs
    it on to reach the credential check at all, including the
    missing-credential-401 assertions."""
    await SqlAlchemyAdminSettingsRepository(db).save_security(
        AdminSecuritySettings(
            id=1,
            enforce_totp=False,
            allow_rfid_login=True,
            allow_local_login=True,
            enable_api_key_auth=True,
            min_password_length=8,
            session_timeout_minutes=1440,
            totp_trusted_device_days=30,
            max_login_attempts=5,
            lockout_duration_minutes=15,
            token_max_lifetime_days=3650,
        )
    )
    await db.commit()


@pytest.fixture
async def key_owner(create_user) -> User:
    """Holds MANAGE_API_KEYS, required to mint or revoke a key at all."""
    return await create_user(
        username="key-owner",
        email="key-owner@example.com",
        permissions=[Permission.MANAGE_API_KEYS],
    )


@pytest.fixture
def mint_api_key(db: Session, key_owner: User) -> Callable[[list[str]], Awaitable[str]]:
    """Mints a real API key via CreateApiKey and returns the raw key
    (visible only at creation)."""

    async def _mint(permissions: list[str]) -> str:
        result = await CreateApiKey(
            SqlAlchemyApiKeyRepository(db),
            SqlAlchemyUserRepository(db),
            SqlAlchemyUnitOfWork(db),
            settings_repo=SqlAlchemyAdminSettingsRepository(db),
            hash_password_fn=aget_hash,
        ).execute(
            actor=key_owner,
            cmd=CreateApiKeyCommand(name="test-key", permissions=permissions, expires_in_days=30),
        )
        return result.key

    return _mint


async def test_key_routers_reject_missing_credential(client: TestClient) -> None:
    """(i) No credential -> 401 on one route of every one of the 3 mounted
    key routers. Deleting `Depends(get_current_api_key_user)` from
    key/router.py:15 (applied once, at router level) turns every one of
    these red at once."""
    for method, path, body in _KEY_ROUTES:
        resp = await client.request(method, path, json=body)
        assert resp.status_code == 401, f"{path} did not reject a missing API key: {resp.text}"


async def test_valid_key_read_succeeds(
    db: Session,
    client: TestClient,
    create_user,
    mint_api_key: Callable[[list[str]], Awaitable[str]],
) -> None:
    """(ii) A valid, unrevoked key reaches the route body. This surface's
    routes carry no per-route permission check beyond authentication (see
    key/endpoints/*.py: none call an *Rules.assert_* with the key's own
    scope), so an empty-permission key still succeeds, resolving the
    badge holder it looks up."""
    rfid = "87654321"
    user = await create_user(username="badge-holder", email="badge@example.com")
    user.rfid_lookup = rfid_lookup(rfid)
    await SqlAlchemyUserRepository(db).save(user)
    await db.commit()

    key = await mint_api_key([])
    resp = await client.post(_RFID_LOOKUP, json={"rfid": rfid}, headers={"X-Api-Key": key})
    assert resp.status_code == 200
    assert resp.json()["username"] == "badge-holder"


async def test_revoked_key_is_rejected(
    db: Session,
    client: TestClient,
    key_owner: User,
    mint_api_key: Callable[[list[str]], Awaitable[str]],
) -> None:
    """(iii) A revoked key is a 401. RevokeApiKey also deactivates the
    key's backing service user in the same transaction, so this exercises
    both the revoked_at check and the is_active check in
    get_current_api_key_user."""
    key = await mint_api_key([])
    created = await CreateApiKey(
        SqlAlchemyApiKeyRepository(db),
        SqlAlchemyUserRepository(db),
        SqlAlchemyUnitOfWork(db),
        settings_repo=SqlAlchemyAdminSettingsRepository(db),
        hash_password_fn=aget_hash,
    ).execute(
        actor=key_owner,
        cmd=CreateApiKeyCommand(name="throwaway", permissions=[], expires_in_days=30),
    )
    await RevokeApiKey(
        SqlAlchemyApiKeyRepository(db), SqlAlchemyUserRepository(db), SqlAlchemyUnitOfWork(db)
    ).execute(actor=key_owner, key_id=created.id)

    resp = await client.post(
        _RFID_LOOKUP, json={"rfid": "00000000"}, headers={"X-Api-Key": created.key}
    )
    assert resp.status_code == 401
    # The untouched fixture key still works, confirms the 401 above is
    # about revocation, not a malformed header.
    resp_ok = await client.post(_RFID_LOOKUP, json={"rfid": "00000000"}, headers={"X-Api-Key": key})
    assert resp_ok.status_code in (200, 404)


async def _badge_holder(db: Session, create_user, rfid: str) -> User:
    user = await create_user(username="badge-holder", email="badge@example.com")
    user.rfid_lookup = rfid_lookup(rfid)
    saved = await SqlAlchemyUserRepository(db).save(user)
    await db.commit()
    return saved


async def test_rfid_lookup_returns_only_the_identity(
    db: Session,
    client: TestClient,
    create_user,
    mint_api_key: Callable[[list[str]], Awaitable[str]],
) -> None:
    """The answer names the tag's owner and carries none of the account's
    details: no e-mail, permissions, groups or login state."""
    holder = await _badge_holder(db, create_user, "87654321")
    key = await mint_api_key([])

    resp = await client.post(_RFID_LOOKUP, json={"rfid": "87654321"}, headers={"X-Api-Key": key})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == {"id", "public_id", "username", "full_name"}
    assert body["id"] == holder.id


async def test_rfid_lookup_honours_the_rfid_setting(
    db: Session,
    client: TestClient,
    create_user,
    mint_api_key: Callable[[list[str]], Awaitable[str]],
) -> None:
    """Switching `allow_rfid_login` off refuses the key surface lookup too,
    not only operator identification on the web surface."""
    await _badge_holder(db, create_user, "87654321")
    key = await mint_api_key([])
    repo = SqlAlchemyAdminSettingsRepository(db)
    security = await repo.get_security()
    security.allow_rfid_login = False
    await repo.save_security(security)
    await db.commit()

    resp = await client.post(_RFID_LOOKUP, json={"rfid": "87654321"}, headers={"X-Api-Key": key})

    assert resp.status_code == 403, resp.text
    assert resp.json()["code"] == "RfidDisabledError"


async def test_rfid_lookup_of_an_unknown_tag_is_404(
    client: TestClient, mint_api_key: Callable[[list[str]], Awaitable[str]]
) -> None:
    key = await mint_api_key([])

    resp = await client.post(_RFID_LOOKUP, json={"rfid": "11112222"}, headers={"X-Api-Key": key})

    assert resp.status_code == 404


async def test_rfid_lookup_no_longer_takes_the_tag_in_the_path(
    client: TestClient, mint_api_key: Callable[[list[str]], Awaitable[str]]
) -> None:
    """The tag travels in the body, so no access log records it."""
    key = await mint_api_key([])

    resp = await client.get(f"{_RFID_LOOKUP}/87654321", headers={"X-Api-Key": key})

    assert resp.status_code in (404, 405)
