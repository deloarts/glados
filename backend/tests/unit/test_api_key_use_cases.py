"""
Unit tests for the API key use cases: creation (including the identity
model, a dedicated backing service-account User per key, and the
permission-ceiling rule), listing, revocation, usage log, and auth-time
key validation.
No database, no HTTP. All dependencies replaced with in-memory fakes.
"""

from dataclasses import replace
from datetime import UTC
from datetime import datetime
from datetime import timedelta

import pytest

from src.modules.platform.adapters.outbound.persistence.pagination import clamp_page
from src.modules.platform.application.dto.api_key_dto import CreateApiKeyCommand
from src.modules.platform.application.services.validate_api_key import ValidateApiKey
from src.modules.platform.application.use_cases.api_key.create_api_key import CreateApiKey
from src.modules.platform.application.use_cases.api_key.get_api_key import GetApiKey
from src.modules.platform.application.use_cases.api_key.get_api_key import GetApiKeys
from src.modules.platform.application.use_cases.api_key.get_api_key_usage_log import (
    GetApiKeyUsageLog,
)
from src.modules.platform.application.use_cases.api_key.revoke_all_api_keys import RevokeAllApiKeys
from src.modules.platform.application.use_cases.api_key.revoke_api_key import RevokeApiKey
from src.modules.platform.const import DEFAULT_PAGE_SIZE
from src.modules.platform.domain.entities.admin_settings.security import AdminSecuritySettings
from src.modules.platform.domain.entities.api_key import ApiKey
from src.modules.platform.domain.entities.api_key_usage_log import ApiKeyUsageLogEntry
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import ApiKeyNotFoundError
from src.modules.platform.domain.exceptions import ExcessiveApiKeyPermissionsError
from src.modules.platform.domain.exceptions import InactiveUserError
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import InvalidTokenError
from src.modules.platform.domain.exceptions import TokenExpiryRequiredError
from src.modules.platform.domain.exceptions import TokenLifetimeExceededError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.security.api_key import hash_api_key
from src.modules.platform.infrastructure.security.hashing import aget_hash
from src.modules.platform.ports.outbound.repositories.api_key_repository import ApiKeyFilterDto
from src.modules.platform.ports.outbound.repositories.api_key_usage_log_repository import (
    ApiKeyUsageLogFilterDto,
)
from tests.factories import make_user

# ── Helpers ───────────────────────────────────────────────────────────


class FakeUserRepository:
    def __init__(self, users: list[User] | None = None):
        self._users: dict[int, User] = {}
        self._next_id = 1
        for u in users or []:
            self._users[u.id] = u
            self._next_id = max(self._next_id, u.id + 1)

    async def get_by_id(self, id: int) -> User | None:
        return self._users.get(id)

    async def get_by_username(self, username: str) -> User | None:
        return next((u for u in self._users.values() if u.username == username), None)

    async def get_by_email(self, email: str) -> User | None:
        return next((u for u in self._users.values() if u.email == email), None)

    async def get_by_rfid(self, rfid: str) -> User | None:
        return None

    async def get_multi(self, filters):
        raise NotImplementedError

    async def save(self, user: User) -> User:
        if user.id == 0:
            user.id = self._next_id
        self._next_id = max(self._next_id, user.id + 1)
        self._users[user.id] = user
        return user

    async def delete(self, user: User) -> None:
        raise NotImplementedError


class FakeApiKeyRepository:
    def __init__(self, keys: list[ApiKey] | None = None):
        self._keys: dict[int, ApiKey] = {}
        self._next_id = 1
        for k in keys or []:
            self._keys[k.id] = k
            self._next_id = max(self._next_id, k.id + 1)

    async def get_by_id(self, id: int) -> ApiKey | None:
        return self._keys.get(id)

    async def get_by_token_hash(self, token_hash: str) -> ApiKey | None:
        return next((k for k in self._keys.values() if k.token_hash == token_hash), None)

    async def get_multi(self, filters: ApiKeyFilterDto) -> tuple[int, list[ApiKey]]:
        results = list(self._keys.values())
        if not filters.include_revoked:
            results = [k for k in results if k.revoked_at is None]
        total = len(results)
        skip = filters.skip or 0
        limit = filters.limit
        return total, results[skip : skip + limit if limit else None]

    async def save(self, key: ApiKey) -> ApiKey:
        if key.id == 0:
            key.id = self._next_id
            self._next_id += 1
        self._keys[key.id] = key
        return key


class FakeApiKeyUsageLogRepository:
    def __init__(self):
        self._entries: list[ApiKeyUsageLogEntry] = []
        self._next_id = 1

    async def append(self, entry: ApiKeyUsageLogEntry) -> ApiKeyUsageLogEntry:
        entry.id = self._next_id
        self._next_id += 1
        self._entries.append(entry)
        return entry

    async def get_by_key_id(
        self, key_id: int, filters: ApiKeyUsageLogFilterDto
    ) -> tuple[int, list[ApiKeyUsageLogEntry]]:
        results = [e for e in self._entries if e.key_id == key_id]
        total = len(results)
        skip = filters.skip or 0
        limit = filters.limit
        return total, results[skip : skip + limit if limit else None]


class FakeUnitOfWork:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


class FakeAdminSettingsRepository:
    """Minimal IAdminSettingsRepository stand-in: CreateApiKey only ever
    calls get_security(), and only reads token_max_lifetime_days."""

    def __init__(self, token_max_lifetime_days: int = 3650):
        self._security = AdminSecuritySettings(
            id=1,
            enforce_totp=False,
            allow_rfid_login=True,
            allow_local_login=True,
            enable_api_key_auth=False,
            min_password_length=8,
            session_timeout_minutes=1440,
            totp_trusted_device_days=30,
            max_login_attempts=5,
            lockout_duration_minutes=15,
            token_max_lifetime_days=token_max_lifetime_days,
        )

    async def get_security(self) -> AdminSecuritySettings:
        return self._security


# ── CreateApiKey ────────────────────────────────────────────────────


class TestCreateApiKey:
    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.key_repo = FakeApiKeyRepository()
        self.user_repo = FakeUserRepository()
        self.uow = FakeUnitOfWork()
        self.settings = FakeAdminSettingsRepository()
        self.actor = make_user(
            id=1,
            permissions=[Permission.MANAGE_API_KEYS, Permission.WRITE_BOUGHT_ITEMS],
        )
        await self.user_repo.save(self.actor)
        self.use_case = CreateApiKey(
            self.key_repo,
            self.user_repo,
            self.uow,
            settings_repo=self.settings,
            hash_password_fn=aget_hash,
        )

    def _cmd(self, **kwargs) -> CreateApiKeyCommand:
        defaults = dict(
            name="CI pipeline", permissions=[Permission.WRITE_BOUGHT_ITEMS], expires_in_days=30
        )
        defaults.update(kwargs)
        return CreateApiKeyCommand(**defaults)

    async def test_creates_successfully(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.name == "CI pipeline"
        assert result.permissions == [Permission.WRITE_BOUGHT_ITEMS]
        assert result.key.startswith("glados_ak_")
        assert self.uow.committed is True

    async def test_creates_dedicated_backing_service_user(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        key = await self.key_repo.get_by_id(result.id)
        service_user = await self.user_repo.get_by_id(key.user_id)
        assert service_user is not None
        assert service_user.id != self.actor.id
        assert service_user.is_service_account is True
        assert service_user.is_systemuser is False
        assert service_user.permissions == [Permission.WRITE_BOUGHT_ITEMS]

    async def test_raw_key_hashes_to_stored_hash(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        key = await self.key_repo.get_by_id(result.id)
        assert key.token_hash == hash_api_key(result.key)

    async def test_unprivileged_user_cannot_create(self):
        actor = make_user(id=2, permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, cmd=self._cmd())

    async def test_cannot_grant_settings_permission(self):
        with pytest.raises(ExcessiveApiKeyPermissionsError):
            await self.use_case.execute(
                actor=self.actor, cmd=self._cmd(permissions=[Permission.READ_SETTINGS])
            )

    async def test_cannot_grant_manage_api_keys(self):
        with pytest.raises(ExcessiveApiKeyPermissionsError):
            await self.use_case.execute(
                actor=self.actor, cmd=self._cmd(permissions=[Permission.MANAGE_API_KEYS])
            )

    async def test_cannot_grant_permission_creator_does_not_hold(self):
        with pytest.raises(ExcessiveApiKeyPermissionsError):
            await self.use_case.execute(
                actor=self.actor, cmd=self._cmd(permissions=[Permission.WRITE_SUPPLIERS])
            )

    async def test_cannot_grant_unknown_permission(self):
        with pytest.raises(ExcessiveApiKeyPermissionsError):
            await self.use_case.execute(
                actor=self.actor, cmd=self._cmd(permissions=["write:nonsense"])
            )

    async def test_systemuser_can_grant_any_non_settings_permission(self):
        actor = make_user(id=3, is_systemuser=True)
        await self.user_repo.save(actor)
        result = await self.use_case.execute(
            actor=actor, cmd=self._cmd(permissions=[Permission.WRITE_SUPPLIERS])
        )
        assert result.permissions == [Permission.WRITE_SUPPLIERS]

    async def test_expiry_is_set_from_expires_in_days(self):
        before = datetime.now(UTC)
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd(expires_in_days=10))
        assert result.expires_at - before >= timedelta(days=9, hours=23)

    async def test_omitted_expires_in_days_means_never_expires_without_a_cap(self):
        self.settings = FakeAdminSettingsRepository(token_max_lifetime_days=0)
        self.use_case = CreateApiKey(
            self.key_repo,
            self.user_repo,
            self.uow,
            settings_repo=self.settings,
            hash_password_fn=aget_hash,
        )
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd(expires_in_days=None))
        assert result.expires_at is None
        assert result.is_expired is False

    # ── Token lifetime cap (Settings polish batch) ──────────────────────

    async def test_expires_in_days_above_the_configured_cap_is_rejected(self):
        self.settings = FakeAdminSettingsRepository(token_max_lifetime_days=30)
        self.use_case = CreateApiKey(
            self.key_repo,
            self.user_repo,
            self.uow,
            settings_repo=self.settings,
            hash_password_fn=aget_hash,
        )
        with pytest.raises(TokenLifetimeExceededError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(expires_in_days=31))

    async def test_expires_in_days_at_the_configured_cap_boundary_succeeds(self):
        self.settings = FakeAdminSettingsRepository(token_max_lifetime_days=30)
        self.use_case = CreateApiKey(
            self.key_repo,
            self.user_repo,
            self.uow,
            settings_repo=self.settings,
            hash_password_fn=aget_hash,
        )
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd(expires_in_days=30))
        assert result.expires_at is not None

    async def test_a_never_expiring_key_is_refused_while_a_cap_is_set(self):
        self.settings = FakeAdminSettingsRepository(token_max_lifetime_days=1)
        self.use_case = CreateApiKey(
            self.key_repo,
            self.user_repo,
            self.uow,
            settings_repo=self.settings,
            hash_password_fn=aget_hash,
        )
        with pytest.raises(TokenExpiryRequiredError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(expires_in_days=None))

    async def test_the_cap_applies_even_to_the_system_user(self):
        """No admin/system carve-out: TokenLifetimeExceededError's docstring
        pins this, the cap applies to every caller equally."""
        system_actor = make_user(id=9, is_systemuser=True)
        await self.user_repo.save(system_actor)
        self.settings = FakeAdminSettingsRepository(token_max_lifetime_days=30)
        self.use_case = CreateApiKey(
            self.key_repo,
            self.user_repo,
            self.uow,
            settings_repo=self.settings,
            hash_password_fn=aget_hash,
        )
        with pytest.raises(TokenLifetimeExceededError):
            await self.use_case.execute(actor=system_actor, cmd=self._cmd(expires_in_days=31))


# ── GetApiKey / GetApiKeys ───────────────────────────────────────────


def make_key(
    id: int = 1,
    name: str = "Test key",
    user_id: int = 100,
    permissions: list[str] | None = None,
    revoked_at: datetime | None = None,
    expires_in_days: int | None = 30,
) -> ApiKey:
    now = datetime.now(UTC)
    return ApiKey(
        id=id,
        name=name,
        token_hash=f"hash-{id}",
        token_prefix=f"glados_ak_prefix{id}",
        user_id=user_id,
        permissions=permissions or [],
        created_by_id=1,
        created=now,
        expires_at=now + timedelta(days=expires_in_days) if expires_in_days is not None else None,
        revoked_at=revoked_at,
    )


class TestGetApiKey:
    def setup_method(self):
        self.key_repo = FakeApiKeyRepository([make_key(id=1), make_key(id=2)])
        self.actor = make_user(permissions=[Permission.MANAGE_API_KEYS])

    async def test_get_existing(self):
        result = await GetApiKey(self.key_repo).execute(actor=self.actor, key_id=1)
        assert result.id == 1

    async def test_get_nonexistent_raises(self):
        with pytest.raises(ApiKeyNotFoundError):
            await GetApiKey(self.key_repo).execute(actor=self.actor, key_id=999)

    async def test_unprivileged_cannot_read(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await GetApiKey(self.key_repo).execute(actor=actor, key_id=1)

    async def test_get_all_excludes_revoked_by_default(self):
        await self.key_repo.save(make_key(id=3, revoked_at=datetime.now(UTC)))
        result = await GetApiKeys(self.key_repo).execute(
            actor=self.actor, filters=ApiKeyFilterDto()
        )
        assert result.total == 2

    async def test_get_all_includes_revoked_when_requested(self):
        await self.key_repo.save(make_key(id=3, revoked_at=datetime.now(UTC)))
        result = await GetApiKeys(self.key_repo).execute(
            actor=self.actor, filters=ApiKeyFilterDto(include_revoked=True)
        )
        assert result.total == 3


# ── RevokeApiKey ──────────────────────────────────────────────────────


class TestRevokeApiKey:
    def setup_method(self):
        self.key = make_key(id=1, user_id=100)
        self.service_user = make_user(id=100, is_service_account=True, permissions=[])
        self.key_repo = FakeApiKeyRepository([self.key])
        self.user_repo = FakeUserRepository([self.service_user])
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.MANAGE_API_KEYS])
        self.use_case = RevokeApiKey(self.key_repo, self.user_repo, self.uow)

    async def test_revokes_successfully(self):
        result = await self.use_case.execute(actor=self.actor, key_id=1)
        assert result.revoked_at is not None
        assert self.uow.committed is True

    async def test_deactivates_backing_service_user(self):
        await self.use_case.execute(actor=self.actor, key_id=1)
        assert (await self.user_repo.get_by_id(100)).is_active is False

    async def test_not_found_raises(self):
        with pytest.raises(ApiKeyNotFoundError):
            await self.use_case.execute(actor=self.actor, key_id=999)

    async def test_unprivileged_cannot_revoke(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, key_id=1)

    async def test_revoking_twice_is_idempotent(self):
        await self.use_case.execute(actor=self.actor, key_id=1)
        result = await self.use_case.execute(actor=self.actor, key_id=1)
        assert result.revoked_at is not None


# ── RevokeAllApiKeys ──────────────────────────────────────────────────


class _OnePagePerCallApiKeyRepository(FakeApiKeyRepository):
    """Pages like the real repository, which clamps every read to one page."""

    async def get_multi(self, filters: ApiKeyFilterDto) -> tuple[int, list[ApiKey]]:
        skip, limit = clamp_page(filters.skip, filters.limit)
        return await super().get_multi(replace(filters, skip=skip, limit=limit))


class TestRevokeAllApiKeys:
    def setup_method(self):
        self.key1 = make_key(id=1, user_id=100)
        self.key2 = make_key(id=2, user_id=101)
        self.service_user1 = make_user(id=100, is_service_account=True, permissions=[])
        self.service_user2 = make_user(id=101, is_service_account=True, permissions=[])
        self.key_repo = FakeApiKeyRepository([self.key1, self.key2])
        self.user_repo = FakeUserRepository([self.service_user1, self.service_user2])
        self.uow = FakeUnitOfWork()
        self.actor = make_user(id=1, permissions=[Permission.MANAGE_API_KEYS])
        self.use_case = RevokeAllApiKeys(self.key_repo, self.user_repo, self.uow)

    async def test_revokes_all_active_keys(self):
        count = await self.use_case.execute(actor=self.actor)
        assert count == 2
        assert (await self.key_repo.get_by_id(1)).revoked_at is not None
        assert (await self.key_repo.get_by_id(2)).revoked_at is not None
        assert self.uow.committed is True

    async def test_deactivates_all_backing_service_users(self):
        await self.use_case.execute(actor=self.actor)
        assert (await self.user_repo.get_by_id(100)).is_active is False
        assert (await self.user_repo.get_by_id(101)).is_active is False

    async def test_revokes_keys_past_the_first_page(self):
        """The real repository answers an omitted limit with one default
        page, so the fake does the same here."""
        keys = [make_key(id=n, user_id=1000 + n) for n in range(1, DEFAULT_PAGE_SIZE + 21)]
        key_repo = _OnePagePerCallApiKeyRepository(keys)
        use_case = RevokeAllApiKeys(key_repo, FakeUserRepository([]), FakeUnitOfWork())

        count = await use_case.execute(actor=self.actor)

        assert count == len(keys)
        assert all(k.revoked_at is not None for k in keys)

    async def test_already_revoked_keys_are_not_recounted(self):
        await self.use_case.execute(actor=self.actor)
        count = await self.use_case.execute(actor=self.actor)
        assert count == 0

    async def test_unprivileged_cannot_revoke_all(self):
        actor = make_user(id=2, permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor)


# ── GetApiKeyUsageLog ─────────────────────────────────────────────────


class TestGetApiKeyUsageLog:
    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.key_repo = FakeApiKeyRepository([make_key(id=1)])
        self.usage_log_repo = FakeApiKeyUsageLogRepository()
        await self.usage_log_repo.append(
            ApiKeyUsageLogEntry(
                id=0,
                key_id=1,
                called_at=datetime.now(UTC),
                method="GET",
                path="/api/v1/key/products/1",
                status_code=200,
            )
        )
        self.actor = make_user(permissions=[Permission.MANAGE_API_KEYS])
        self.use_case = GetApiKeyUsageLog(self.key_repo, self.usage_log_repo)

    async def test_returns_entries_for_key(self):
        result = await self.use_case.execute(
            actor=self.actor, key_id=1, filters=ApiKeyUsageLogFilterDto()
        )
        assert result.total == 1
        assert result.items[0].path == "/api/v1/key/products/1"

    async def test_unknown_key_raises(self):
        with pytest.raises(ApiKeyNotFoundError):
            await self.use_case.execute(
                actor=self.actor, key_id=999, filters=ApiKeyUsageLogFilterDto()
            )

    async def test_unprivileged_cannot_read(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, key_id=1, filters=ApiKeyUsageLogFilterDto())


# ── ValidateApiKey ────────────────────────────────────────────────────


class TestValidateApiKey:
    def setup_method(self):
        self.raw_key = "glados_ak_test-key-value"
        self.service_user = make_user(id=100, is_service_account=True, permissions=["write:x"])
        self.key = make_key(id=1, user_id=100)
        self.key.token_hash = hash_api_key(self.raw_key)
        self.key_repo = FakeApiKeyRepository([self.key])
        self.user_repo = FakeUserRepository([self.service_user])
        self.use_case = ValidateApiKey(self.key_repo, self.user_repo, hash_fn=hash_api_key)

    async def test_valid_key_returns_service_user(self):
        user, key_id = await self.use_case.execute(self.raw_key)
        assert user.id == 100
        assert key_id == 1

    async def test_empty_key_raises(self):
        with pytest.raises(InvalidTokenError):
            await self.use_case.execute("")

    async def test_unknown_key_raises(self):
        with pytest.raises(InvalidTokenError):
            await self.use_case.execute("glados_ak_does-not-exist")

    async def test_revoked_key_raises(self):
        self.key.revoked_at = datetime.now(UTC)
        with pytest.raises(InvalidTokenError):
            await self.use_case.execute(self.raw_key)

    async def test_expired_key_raises(self):
        self.key.expires_at = datetime.now(UTC) - timedelta(days=1)
        with pytest.raises(InvalidTokenError):
            await self.use_case.execute(self.raw_key)

    async def test_non_expiring_key_never_raises_expired(self):
        self.key.expires_at = None
        user, _key_id = await self.use_case.execute(self.raw_key)
        assert user.id == 100

    async def test_inactive_backing_user_raises(self):
        self.service_user.is_active = False
        with pytest.raises(InactiveUserError):
            await self.use_case.execute(self.raw_key)
