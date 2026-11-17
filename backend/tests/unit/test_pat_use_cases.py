"""
Unit tests for the personal access token (PAT) use cases: creation
(including the permission-ceiling rule), listing, revocation, usage log,
and auth-time token validation, including the impersonation-with-scoping
identity model (a PAT authenticates as its owning User, but with
permissions capped to the token's own grant, not the full user).
No database, no HTTP. All dependencies replaced with in-memory fakes.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta

import pytest

from src.modules.platform.application.dto.pat_dto import CreatePatCommand
from src.modules.platform.application.use_cases.pat.create_pat import CreatePat
from src.modules.platform.application.use_cases.pat.get_pat import GetPat
from src.modules.platform.application.use_cases.pat.get_pat import GetPats
from src.modules.platform.application.use_cases.pat.get_pat_usage_log import GetPatUsageLog
from src.modules.platform.application.use_cases.pat.revoke_all_pats import RevokeAllPats
from src.modules.platform.application.use_cases.pat.revoke_pat import RevokePat
from src.modules.platform.application.use_cases.pat.validate_pat import ValidatePat
from src.modules.platform.domain.entities.admin_settings.security import AdminSecuritySettings
from src.modules.platform.domain.entities.pat_usage_log import PatUsageLogEntry
from src.modules.platform.domain.entities.personal_access_token import PersonalAccessToken
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import ExcessivePatPermissionsError
from src.modules.platform.domain.exceptions import InactiveUserError
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import InvalidTokenError
from src.modules.platform.domain.exceptions import PatNotFoundError
from src.modules.platform.domain.exceptions import TokenExpiryRequiredError
from src.modules.platform.domain.exceptions import TokenLifetimeExceededError
from src.modules.platform.domain.services.pat_rules import PatRules
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.security.pat import hash_pat
from src.modules.platform.ports.outbound.repositories.pat_repository import PatFilterDto
from src.modules.platform.ports.outbound.repositories.pat_usage_log_repository import (
    PatUsageLogFilterDto,
)
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork

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


class FakePatRepository:
    def __init__(self, tokens: list[PersonalAccessToken] | None = None):
        self._tokens: dict[int, PersonalAccessToken] = {}
        self._next_id = 1
        for t in tokens or []:
            self._tokens[t.id] = t
            self._next_id = max(self._next_id, t.id + 1)

    @property
    def tokens(self) -> dict[int, PersonalAccessToken]:
        """The stored tokens by id, for assertions."""
        return self._tokens

    async def get_by_id(self, id: int) -> PersonalAccessToken | None:
        return self._tokens.get(id)

    async def get_by_token_hash(self, token_hash: str) -> PersonalAccessToken | None:
        return next((t for t in self._tokens.values() if t.token_hash == token_hash), None)

    async def get_multi_for_user(
        self, user_id: int, filters: PatFilterDto
    ) -> tuple[int, list[PersonalAccessToken]]:
        results = [t for t in self._tokens.values() if t.user_id == user_id]
        if not filters.include_revoked:
            results = [t for t in results if t.revoked_at is None]
        total = len(results)
        skip = filters.skip or 0
        limit = filters.limit
        return total, results[skip : skip + limit if limit else None]

    async def save(self, token: PersonalAccessToken) -> PersonalAccessToken:
        if token.id == 0:
            token.id = self._next_id
            self._next_id += 1
        self._tokens[token.id] = token
        return token

    async def revoke_all_for_user(self, user_id: int) -> int:
        now = datetime.now(UTC)
        count = 0
        for t in self._tokens.values():
            if t.user_id == user_id and t.revoked_at is None:
                t.revoked_at = now
                count += 1
        return count


class FakePatUsageLogRepository:
    def __init__(self):
        self._entries: list[PatUsageLogEntry] = []
        self._next_id = 1

    async def append(self, entry: PatUsageLogEntry) -> PatUsageLogEntry:
        entry.id = self._next_id
        self._next_id += 1
        self._entries.append(entry)
        return entry

    async def get_by_pat_id(
        self, pat_id: int, filters: PatUsageLogFilterDto
    ) -> tuple[int, list[PatUsageLogEntry]]:
        results = [e for e in self._entries if e.pat_id == pat_id]
        total = len(results)
        skip = filters.skip or 0
        limit = filters.limit
        return total, results[skip : skip + limit if limit else None]


class FakeAdminSettingsRepository:
    """Minimal IAdminSettingsRepository stand-in: CreatePat only ever calls
    get_security(), and only reads token_max_lifetime_days."""

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


# ── PatRules.assert_can_create ──────────────────────────────────────


class TestAssertCanCreateRefusesSystemUser:
    def test_system_user_is_refused_regardless_of_permissions(self):
        """Ordering matters: User.has_permission returns True for every
        permission when is_systemuser, so the flag must be checked before
        the permission below or this would never fire."""
        system_actor = make_user(id=9, is_systemuser=True)
        with pytest.raises(InsufficientPermissionsError):
            PatRules.assert_can_create(system_actor)

    def test_an_ordinary_user_with_the_permission_is_unaffected(self):
        PatRules.assert_can_create(make_user(id=1, permissions=[Permission.WRITE_PAT]))


# ── CreatePat ─────────────────────────────────────────────────────────


class TestCreatePat:
    def setup_method(self):
        self.pat_repo = FakePatRepository()
        self.settings = FakeAdminSettingsRepository()
        self.actor = make_user(
            id=1, permissions=[Permission.WRITE_PAT, Permission.WRITE_BOUGHT_ITEMS]
        )
        self.use_case = CreatePat(self.pat_repo, settings_repo=self.settings, uow=FakeUnitOfWork())

    def _cmd(self, **kwargs) -> CreatePatCommand:
        defaults = dict(
            name="Local dev", permissions=[Permission.WRITE_BOUGHT_ITEMS], expires_in_days=30
        )
        defaults.update(kwargs)
        return CreatePatCommand(**defaults)

    async def test_creates_successfully(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.name == "Local dev"
        assert result.permissions == [Permission.WRITE_BOUGHT_ITEMS]
        assert result.token.startswith("glados_pat_")

    async def test_does_not_create_a_new_user(self):
        """Unlike an API key, a PAT authenticates as the actor themselves,
        no backing service-account row should be created."""
        before = len(self.pat_repo._tokens)
        await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        # Only the token was persisted; there's no user repo write to check
        # here since CreatePat doesn't even depend on IUserRepository.
        assert len(self.pat_repo.tokens) == before + 1

    async def test_raw_token_hashes_to_stored_hash(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        token = await self.pat_repo.get_by_id(result.id)
        assert token.token_hash == hash_pat(result.token)
        assert token.user_id == self.actor.id

    async def test_unprivileged_user_cannot_create(self):
        actor = make_user(id=2, permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, cmd=self._cmd())

    async def test_cannot_grant_settings_permission(self):
        with pytest.raises(ExcessivePatPermissionsError):
            await self.use_case.execute(
                actor=self.actor, cmd=self._cmd(permissions=[Permission.READ_SETTINGS])
            )

    async def test_cannot_grant_manage_api_keys(self):
        with pytest.raises(ExcessivePatPermissionsError):
            await self.use_case.execute(
                actor=self.actor, cmd=self._cmd(permissions=[Permission.MANAGE_API_KEYS])
            )

    async def test_cannot_grant_permission_creator_does_not_hold(self):
        with pytest.raises(ExcessivePatPermissionsError):
            await self.use_case.execute(
                actor=self.actor, cmd=self._cmd(permissions=[Permission.WRITE_SUPPLIERS])
            )

    async def test_cannot_grant_unknown_permission(self):
        with pytest.raises(ExcessivePatPermissionsError):
            await self.use_case.execute(
                actor=self.actor, cmd=self._cmd(permissions=["write:nonsense"])
            )

    async def test_systemuser_cannot_create_a_pat(self):
        """The system account cannot create personal access tokens at all
        (see PatRules.assert_can_create), checked before the permission
        grant is even considered."""
        actor = make_user(id=3, is_systemuser=True)
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(
                actor=actor, cmd=self._cmd(permissions=[Permission.WRITE_SUPPLIERS])
            )

    async def test_expiry_is_set_from_expires_in_days(self):
        before = datetime.now(UTC)
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd(expires_in_days=10))
        assert result.expires_at - before >= timedelta(days=9, hours=23)

    async def test_omitted_expires_in_days_means_never_expires_without_a_cap(self):
        self.settings = FakeAdminSettingsRepository(token_max_lifetime_days=0)
        self.use_case = CreatePat(self.pat_repo, settings_repo=self.settings, uow=FakeUnitOfWork())
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd(expires_in_days=None))
        assert result.expires_at is None
        assert result.is_expired is False

    async def test_multiple_tokens_can_coexist_for_same_user(self):
        first = await self.use_case.execute(actor=self.actor, cmd=self._cmd(name="Token A"))
        second = await self.use_case.execute(actor=self.actor, cmd=self._cmd(name="Token B"))
        assert first.id != second.id
        total, _tokens = await self.pat_repo.get_multi_for_user(self.actor.id, PatFilterDto())
        assert total == 2

    # ── Token lifetime cap (Settings polish batch) ──────────────────────

    async def test_expires_in_days_above_the_configured_cap_is_rejected(self):
        self.settings = FakeAdminSettingsRepository(token_max_lifetime_days=30)
        self.use_case = CreatePat(self.pat_repo, settings_repo=self.settings, uow=FakeUnitOfWork())
        with pytest.raises(TokenLifetimeExceededError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(expires_in_days=31))

    async def test_expires_in_days_at_the_configured_cap_boundary_succeeds(self):
        self.settings = FakeAdminSettingsRepository(token_max_lifetime_days=30)
        self.use_case = CreatePat(self.pat_repo, settings_repo=self.settings, uow=FakeUnitOfWork())
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd(expires_in_days=30))
        assert result.expires_at is not None

    async def test_a_never_expiring_token_is_refused_while_a_cap_is_set(self):
        self.settings = FakeAdminSettingsRepository(token_max_lifetime_days=1)
        self.use_case = CreatePat(self.pat_repo, settings_repo=self.settings, uow=FakeUnitOfWork())
        with pytest.raises(TokenExpiryRequiredError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(expires_in_days=None))


# ── GetPat / GetPats ─────────────────────────────────────────────────


def make_token(
    id: int = 1,
    name: str = "Test token",
    user_id: int = 1,
    permissions: list[str] | None = None,
    revoked_at: datetime | None = None,
    expires_in_days: int | None = 30,
) -> PersonalAccessToken:
    now = datetime.now(UTC)
    return PersonalAccessToken(
        id=id,
        name=name,
        token_hash=f"hash-{id}",
        token_prefix=f"glados_pat_prefix{id}",
        user_id=user_id,
        permissions=permissions or [],
        created=now,
        expires_at=now + timedelta(days=expires_in_days) if expires_in_days is not None else None,
        revoked_at=revoked_at,
    )


class TestGetPat:
    def setup_method(self):
        self.pat_repo = FakePatRepository(
            [make_token(id=1, user_id=1), make_token(id=2, user_id=1)]
        )
        self.actor = make_user(id=1)

    async def test_get_existing(self):
        result = await GetPat(self.pat_repo).execute(actor=self.actor, pat_id=1)
        assert result.id == 1

    async def test_get_nonexistent_raises(self):
        with pytest.raises(PatNotFoundError):
            await GetPat(self.pat_repo).execute(actor=self.actor, pat_id=999)

    async def test_owner_can_read_own_token(self):
        result = await GetPat(self.pat_repo).execute(actor=self.actor, pat_id=1)
        assert result.id == 1

    async def test_non_owner_without_write_settings_cannot_read(self):
        other = make_user(id=2, permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await GetPat(self.pat_repo).execute(actor=other, pat_id=1)

    async def test_admin_with_write_settings_can_read_others_token(self):
        admin = make_user(id=2, permissions=[Permission.WRITE_SETTINGS])
        result = await GetPat(self.pat_repo).execute(actor=admin, pat_id=1)
        assert result.id == 1

    async def test_get_all_scoped_to_actor_only(self):
        await self.pat_repo.save(make_token(id=3, user_id=999))
        result = await GetPats(self.pat_repo).execute(actor=self.actor, filters=PatFilterDto())
        assert result.total == 2

    async def test_get_all_excludes_revoked_by_default(self):
        await self.pat_repo.save(make_token(id=3, user_id=1, revoked_at=datetime.now(UTC)))
        result = await GetPats(self.pat_repo).execute(actor=self.actor, filters=PatFilterDto())
        assert result.total == 2

    async def test_get_all_includes_revoked_when_requested(self):
        await self.pat_repo.save(make_token(id=3, user_id=1, revoked_at=datetime.now(UTC)))
        result = await GetPats(self.pat_repo).execute(
            actor=self.actor, filters=PatFilterDto(include_revoked=True)
        )
        assert result.total == 3


# ── RevokePat ─────────────────────────────────────────────────────────


class TestRevokePat:
    def setup_method(self):
        self.token = make_token(id=1, user_id=1)
        self.pat_repo = FakePatRepository([self.token])
        self.actor = make_user(id=1)
        self.use_case = RevokePat(self.pat_repo, uow=FakeUnitOfWork())

    async def test_owner_revokes_successfully(self):
        result = await self.use_case.execute(actor=self.actor, pat_id=1)
        assert result.revoked_at is not None

    async def test_not_found_raises(self):
        with pytest.raises(PatNotFoundError):
            await self.use_case.execute(actor=self.actor, pat_id=999)

    async def test_non_owner_without_write_settings_cannot_revoke(self):
        other = make_user(id=2, permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=other, pat_id=1)

    async def test_admin_with_write_settings_can_revoke_others_token(self):
        admin = make_user(id=2, permissions=[Permission.WRITE_SETTINGS])
        result = await self.use_case.execute(actor=admin, pat_id=1)
        assert result.revoked_at is not None

    async def test_revoking_twice_is_idempotent(self):
        await self.use_case.execute(actor=self.actor, pat_id=1)
        result = await self.use_case.execute(actor=self.actor, pat_id=1)
        assert result.revoked_at is not None


# ── RevokeAllPats ─────────────────────────────────────────────────────


class TestRevokeAllPats:
    def setup_method(self):
        self.pat_repo = FakePatRepository(
            [
                make_token(id=1, user_id=1),
                make_token(id=2, user_id=1),
                make_token(id=3, user_id=2),
            ]
        )
        self.actor = make_user(id=1)
        self.use_case = RevokeAllPats(self.pat_repo, uow=FakeUnitOfWork())

    async def test_revokes_only_actors_own_tokens(self):
        count = await self.use_case.execute(actor=self.actor)
        assert count == 2
        assert (await self.pat_repo.get_by_id(1)).revoked_at is not None
        assert (await self.pat_repo.get_by_id(2)).revoked_at is not None
        assert (await self.pat_repo.get_by_id(3)).revoked_at is None

    async def test_already_revoked_tokens_are_not_recounted(self):
        await self.use_case.execute(actor=self.actor)
        count = await self.use_case.execute(actor=self.actor)
        assert count == 0

    async def test_no_tokens_returns_zero(self):
        actor = make_user(id=99)
        count = await self.use_case.execute(actor=actor)
        assert count == 0


# ── GetPatUsageLog ────────────────────────────────────────────────────


class TestGetPatUsageLog:
    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.pat_repo = FakePatRepository([make_token(id=1, user_id=1)])
        self.usage_log_repo = FakePatUsageLogRepository()
        await self.usage_log_repo.append(
            PatUsageLogEntry(
                id=0,
                pat_id=1,
                called_at=datetime.now(UTC),
                method="GET",
                path="/api/v1/web/products/1",
                status_code=200,
            )
        )
        self.actor = make_user(id=1)
        self.use_case = GetPatUsageLog(self.pat_repo, self.usage_log_repo)

    async def test_returns_entries_for_token(self):
        result = await self.use_case.execute(
            actor=self.actor, pat_id=1, filters=PatUsageLogFilterDto()
        )
        assert result.total == 1
        assert result.items[0].path == "/api/v1/web/products/1"

    async def test_unknown_token_raises(self):
        with pytest.raises(PatNotFoundError):
            await self.use_case.execute(
                actor=self.actor, pat_id=999, filters=PatUsageLogFilterDto()
            )

    async def test_non_owner_without_write_settings_cannot_read(self):
        other = make_user(id=2, permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=other, pat_id=1, filters=PatUsageLogFilterDto())


# ── ValidatePat ───────────────────────────────────────────────────────


class TestValidatePat:
    def setup_method(self):
        self.raw_token = "glados_pat_test-token-value"
        self.owner = make_user(
            id=1, permissions=[Permission.WRITE_BOUGHT_ITEMS, Permission.WRITE_SUPPLIERS]
        )
        self.token = make_token(id=1, user_id=1, permissions=[Permission.WRITE_BOUGHT_ITEMS])
        self.token.token_hash = hash_pat(self.raw_token)
        self.pat_repo = FakePatRepository([self.token])
        self.user_repo = FakeUserRepository([self.owner])
        self.use_case = ValidatePat(self.pat_repo, self.user_repo, hash_fn=hash_pat)

    async def test_valid_token_returns_owning_user(self):
        user, pat_id = await self.use_case.execute(self.raw_token)
        assert user.id == 1
        assert pat_id == 1

    async def test_returned_user_permissions_are_capped_to_token_scope(self):
        """The owner holds write:bought_items AND write:suppliers, but this
        token was only ever granted write:bought_items, the effective
        principal must not carry the owner's full permission set."""
        user, _ = await self.use_case.execute(self.raw_token)
        assert user.has_permission(Permission.WRITE_BOUGHT_ITEMS) is True
        assert user.has_permission(Permission.WRITE_SUPPLIERS) is False

    async def test_systemuser_owned_token_is_refused(self):
        """PatRules.assert_can_create refuses to mint a new one, and a
        system-user token that exists anyway must not validate either,
        regardless of what it was scoped to."""
        sys_owner = make_user(id=2, is_systemuser=True)
        token = make_token(id=2, user_id=2, permissions=[Permission.WRITE_BOUGHT_ITEMS])
        token.token_hash = hash_pat("glados_pat_sys-token")
        pat_repo = FakePatRepository([token])
        user_repo = FakeUserRepository([sys_owner])
        use_case = ValidatePat(pat_repo, user_repo, hash_fn=hash_pat)

        with pytest.raises(InvalidTokenError):
            await use_case.execute("glados_pat_sys-token")

    async def test_empty_token_raises(self):
        with pytest.raises(InvalidTokenError):
            await self.use_case.execute("")

    async def test_unknown_token_raises(self):
        with pytest.raises(InvalidTokenError):
            await self.use_case.execute("glados_pat_does-not-exist")

    async def test_revoked_token_raises(self):
        self.token.revoked_at = datetime.now(UTC)
        with pytest.raises(InvalidTokenError):
            await self.use_case.execute(self.raw_token)

    async def test_expired_token_raises(self):
        self.token.expires_at = datetime.now(UTC) - timedelta(days=1)
        with pytest.raises(InvalidTokenError):
            await self.use_case.execute(self.raw_token)

    async def test_non_expiring_token_never_raises_expired(self):
        self.token.expires_at = None
        user, _ = await self.use_case.execute(self.raw_token)
        assert user.id == 1

    async def test_inactive_owner_raises(self):
        self.owner.is_active = False
        with pytest.raises(InactiveUserError):
            await self.use_case.execute(self.raw_token)
