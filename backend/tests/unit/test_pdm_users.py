"""
Unit tests for PDM user matching: resolve_pdm_user (the shared resolution
service ingest attribution and ListPdmUsers both use), ListPdmUsers (the
admin console's vault-users-vs-Glados-users listing) and LinkPdmUsers (the
matching dialog's save action). No database, no HTTP: every port is an
in-memory fake.
"""

from datetime import UTC
from datetime import datetime
from typing import Any

import pytest

from src.modules.external_data.application.dto.admin_settings_dto.pdm_vault import (
    LinkPdmUserEntryCommand,
)
from src.modules.external_data.application.dto.admin_settings_dto.pdm_vault import (
    LinkPdmUsersCommand,
)
from src.modules.external_data.application.services.pdm_session import PdmSessionService
from src.modules.external_data.application.services.pdm_users import resolve_pdm_user
from src.modules.external_data.application.use_cases.admin_settings.link_pdm_users import (
    LinkPdmUsers,
)
from src.modules.external_data.application.use_cases.admin_settings.list_pdm_users import (
    ListPdmUsers,
)
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.errors import PdmApiError
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmAuthResult
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmUser
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmUserExtended
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.entities.user_pdm_link import UserPdmLink
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import UserNotFoundError
from src.modules.platform.domain.value_objects.permission import Permission
from tests import factories
from tests.unit.fakes import FakeUnitOfWork


def make_user(*, permissions: list[str] | None = None, **overrides: Any) -> User:
    """A user who may write settings unless the test passes other permissions."""
    if permissions is None:
        permissions = [Permission.WRITE_SETTINGS]
    return factories.make_user(permissions=permissions, **overrides)


class FakeUserRepository:
    def __init__(self, users: list[User] | None = None) -> None:
        self._users: dict[int, User] = {u.id: u for u in (users or [])}

    async def get_by_id(self, id: int) -> User | None:
        return self._users.get(id)

    async def get_by_username_ci(self, username: str) -> User | None:
        value = username.strip().lower()
        return next((u for u in self._users.values() if u.username.lower() == value), None)

    async def get_by_email_ci(self, email: str) -> User | None:
        value = email.strip().lower()
        for user in self._users.values():
            if user.email.lower() == value:
                return user
        return None

    async def save(self, user: User) -> User:
        self._users[user.id] = user
        return user


class FakeUserPdmLinkRepository:
    """In-memory double for IUserPdmLinkRepository, keyed on pdm_user_id
    exactly like the real unique constraint."""

    def __init__(self, links: list[UserPdmLink] | None = None) -> None:
        self._by_pdm_user_id: dict[int, UserPdmLink] = {
            link.pdm_user_id: link for link in (links or [])
        }
        self._next_id = max((link.id for link in (links or [])), default=0) + 1

    async def list_all(self) -> list[UserPdmLink]:
        return list(self._by_pdm_user_id.values())

    async def list_by_user(self, user_id: int) -> list[UserPdmLink]:
        return [link for link in self._by_pdm_user_id.values() if link.user_id == user_id]

    async def get_by_pdm_user_id(self, pdm_user_id: int) -> UserPdmLink | None:
        return self._by_pdm_user_id.get(pdm_user_id)

    async def upsert(self, *, pdm_user_id: int, user_id: int, pdm_username: str) -> UserPdmLink:
        existing = self._by_pdm_user_id.get(pdm_user_id)
        link = UserPdmLink(
            id=existing.id if existing is not None else self._next_id,
            user_id=user_id,
            pdm_user_id=pdm_user_id,
            pdm_username=pdm_username,
            linked_at=datetime.now(UTC),
        )
        if existing is None:
            self._next_id += 1
        self._by_pdm_user_id[pdm_user_id] = link
        return link

    async def delete_by_pdm_user_id(self, pdm_user_id: int) -> None:
        self._by_pdm_user_id.pop(pdm_user_id, None)


class FakeAdminSettingsRepository:
    def __init__(self, settings: AdminPdmSettings) -> None:
        self._settings = settings
        self.save_session_calls: list[dict[str, object]] = []

    async def get_pdm(self) -> AdminPdmSettings:
        return self._settings

    async def save_pdm_session(
        self, *, token: str | None, user_id: int | None, obtained_at: datetime | None
    ) -> None:
        self.save_session_calls.append(
            {"token": token, "user_id": user_id, "obtained_at": obtained_at}
        )
        self._settings.session_token = token
        self._settings.session_user_id = user_id
        self._settings.session_obtained_at = obtained_at


class FakeGateway:
    def __init__(
        self,
        *,
        users: list[PdmUser] | None = None,
        extended_by_id: dict[int, PdmUserExtended] | None = None,
        extended_error: Exception | None = None,
    ) -> None:
        self._users = users or []
        self._extended_by_id = extended_by_id or {}
        self._extended_error = extended_error
        self.extended_calls: list[int] = []

    async def authenticate(self, username: str, password: str) -> PdmAuthResult:
        return PdmAuthResult(token="fake-token", user_id=1)

    async def list_users(self, token: str) -> list[PdmUser]:
        return list(self._users)

    async def user_extended(self, token: str, user_id: int) -> PdmUserExtended:
        self.extended_calls.append(user_id)
        if self._extended_error is not None:
            raise self._extended_error
        return self._extended_by_id[user_id]


def make_pdm_settings(**overrides: object) -> AdminPdmSettings:
    defaults: dict[str, object] = {
        "id": 1,
        "made_item_variable_map": {},
        "bought_item_variable_map": {},
        "enabled": False,
        "base_url": "http://pdm-host:65453",
        "vault_name": "MyVault",
        "username": "svc-account",
        "password": "secret",
        "verify_certificate": True,
        "timeout_seconds": 15,
        "session_token": None,
        "session_user_id": None,
        "session_obtained_at": None,
        "watched_folders": [],
        "made_released_state_ids": [],
        "made_obsolete_state_ids": [],
        "made_replaced_state_ids": [],
        "bought_released_state_ids": [],
        "bought_obsolete_state_ids": [],
        "bought_replaced_state_ids": [],
        "poll_interval_minutes": 15,
        "vault_id": "",
        "cad_items_read_only": True,
        "last_poll_at": None,
        "last_poll_error": None,
        "last_poll_summary": None,
        "writeback_enabled": False,
        "made_item_extensions": ["sldprt"],
        "bought_item_extensions": ["sldprt", "sldasm"],
        "document_categories": {},
        "thumbnails_enabled": False,
        "stuck_after_days": 7,
        "reconcile_requested_deep": None,
        "required_fields": {"made": [], "bought": []},
    }
    defaults.update(overrides)
    return AdminPdmSettings(**defaults)  # type: ignore[arg-type]


def make_session(gateway: FakeGateway, settings: AdminPdmSettings) -> PdmSessionService:
    return PdmSessionService(
        repo=FakeAdminSettingsRepository(settings), gateway_factory=lambda connection: gateway
    )


# ── resolve_pdm_user ─────────────────────────────────────────────────


class TestResolvePdmUser:
    async def test_link_wins(self) -> None:
        linked = make_user(id=5, username="alice")
        user_repo = FakeUserRepository([linked, make_user(id=6, username="bob")])
        link_repo = FakeUserPdmLinkRepository(
            [
                UserPdmLink(
                    id=1,
                    user_id=5,
                    pdm_user_id=42,
                    pdm_username="alice",
                    linked_at=datetime.now(UTC),
                )
            ]
        )
        resolved = await resolve_pdm_user(link_repo, user_repo, 42, "someone-else")
        assert resolved is linked

    async def test_falls_back_to_case_insensitive_username(self) -> None:
        user = make_user(id=6, username="Bob.Smith")
        user_repo = FakeUserRepository([user])
        link_repo = FakeUserPdmLinkRepository([])
        resolved = await resolve_pdm_user(link_repo, user_repo, None, "bob.smith")
        assert resolved is user

    async def test_no_match_returns_none(self) -> None:
        user_repo = FakeUserRepository([make_user(id=1, username="alice")])
        link_repo = FakeUserPdmLinkRepository([])
        assert await resolve_pdm_user(link_repo, user_repo, 99, "nobody") is None

    async def test_blank_username_returns_none_without_lookup(self) -> None:
        user_repo = FakeUserRepository([])
        link_repo = FakeUserPdmLinkRepository([])
        assert await resolve_pdm_user(link_repo, user_repo, None, "   ") is None

    async def test_link_to_a_deleted_user_falls_back_to_username(self) -> None:
        """A link row surviving without its target (should not happen with
        the FK's ON DELETE CASCADE, but resolve_pdm_user does not assume
        it) falls through to the username guess rather than raising."""
        user = make_user(id=6, username="fallback")
        user_repo = FakeUserRepository([user])
        link_repo = FakeUserPdmLinkRepository(
            [
                UserPdmLink(
                    id=1,
                    user_id=999,
                    pdm_user_id=42,
                    pdm_username="ghost",
                    linked_at=datetime.now(UTC),
                )
            ]
        )
        resolved = await resolve_pdm_user(link_repo, user_repo, 42, "fallback")
        assert resolved is user


# ── ListPdmUsers ─────────────────────────────────────────────────────


class TestListPdmUsers:
    async def test_requires_write_settings_permission(self) -> None:
        gateway = FakeGateway(users=[])
        settings = make_pdm_settings()
        use_case = ListPdmUsers(
            session=make_session(gateway, settings),
            settings_repo=FakeAdminSettingsRepository(settings),
            user_repo=FakeUserRepository([]),
            link_repo=FakeUserPdmLinkRepository([]),
        )
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(actor)

    async def test_linked_user_is_reported_and_not_proposed(self) -> None:
        linked = make_user(id=5, username="jdoe")
        gateway = FakeGateway(users=[PdmUser(id=2, username="jdoe", full_name="Jane Doe")])
        settings = make_pdm_settings()
        link_repo = FakeUserPdmLinkRepository(
            [
                UserPdmLink(
                    id=1, user_id=5, pdm_user_id=2, pdm_username="jdoe", linked_at=datetime.now(UTC)
                )
            ]
        )
        use_case = ListPdmUsers(
            session=make_session(gateway, settings),
            settings_repo=FakeAdminSettingsRepository(settings),
            user_repo=FakeUserRepository([linked]),
            link_repo=link_repo,
        )
        [row] = await use_case.execute(make_user())
        assert row.pdm_user_id == 2
        assert row.linked_user_id == 5
        assert row.proposed_user_id is None
        assert row.is_service_account is False

    async def test_several_vault_users_may_link_to_the_same_glados_user(self) -> None:
        shared = make_user(id=5, username="jdoe")
        gateway = FakeGateway(
            users=[
                PdmUser(id=2, username="jdoe", full_name="Jane Doe"),
                PdmUser(id=3, username="jdoe.alt", full_name="Jane Doe (alt account)"),
            ]
        )
        settings = make_pdm_settings()
        link_repo = FakeUserPdmLinkRepository(
            [
                UserPdmLink(
                    id=1, user_id=5, pdm_user_id=2, pdm_username="jdoe", linked_at=datetime.now(UTC)
                ),
                UserPdmLink(
                    id=2,
                    user_id=5,
                    pdm_user_id=3,
                    pdm_username="jdoe.alt",
                    linked_at=datetime.now(UTC),
                ),
            ]
        )
        use_case = ListPdmUsers(
            session=make_session(gateway, settings),
            settings_repo=FakeAdminSettingsRepository(settings),
            user_repo=FakeUserRepository([shared]),
            link_repo=link_repo,
        )
        rows = {row.pdm_user_id: row for row in await use_case.execute(make_user())}
        assert rows[2].linked_user_id == 5
        assert rows[3].linked_user_id == 5

    async def test_service_account_is_flagged_and_never_proposed(self) -> None:
        gateway = FakeGateway(
            users=[PdmUser(id=3, username="svc-account", full_name="Service Account")]
        )
        settings = make_pdm_settings(username="svc-account")
        use_case = ListPdmUsers(
            session=make_session(gateway, settings),
            settings_repo=FakeAdminSettingsRepository(settings),
            user_repo=FakeUserRepository([]),
            link_repo=FakeUserPdmLinkRepository([]),
        )
        [row] = await use_case.execute(make_user())
        assert row.is_service_account is True
        assert row.linked_user_id is None
        assert row.proposed_user_id is None

    async def test_unlinked_user_proposed_by_case_insensitive_username(self) -> None:
        candidate = make_user(id=7, username="Jdoe")
        gateway = FakeGateway(users=[PdmUser(id=2, username="jdoe", full_name="Jane Doe")])
        settings = make_pdm_settings()
        use_case = ListPdmUsers(
            session=make_session(gateway, settings),
            settings_repo=FakeAdminSettingsRepository(settings),
            user_repo=FakeUserRepository([candidate]),
            link_repo=FakeUserPdmLinkRepository([]),
        )
        [row] = await use_case.execute(make_user())
        assert row.proposed_user_id == 7

    async def test_unlinked_user_proposed_by_email_when_username_does_not_match(self) -> None:
        candidate = make_user(id=8, username="glados-jane", email="jane.doe@example.com")
        gateway = FakeGateway(
            users=[PdmUser(id=2, username="jdoe", full_name="Jane Doe")],
            extended_by_id={
                2: PdmUserExtended(
                    id=2, username="jdoe", full_name="Jane Doe", email="jane.doe@example.com"
                )
            },
        )
        settings = make_pdm_settings()
        use_case = ListPdmUsers(
            session=make_session(gateway, settings),
            settings_repo=FakeAdminSettingsRepository(settings),
            user_repo=FakeUserRepository([candidate]),
            link_repo=FakeUserPdmLinkRepository([]),
        )
        [row] = await use_case.execute(make_user())
        assert row.proposed_user_id == 8
        assert gateway.extended_calls == [2]

    async def test_no_match_at_all_leaves_proposal_none(self) -> None:
        gateway = FakeGateway(
            users=[PdmUser(id=2, username="jdoe", full_name="Jane Doe")],
            extended_by_id={
                2: PdmUserExtended(id=2, username="jdoe", full_name="Jane Doe", email="")
            },
        )
        settings = make_pdm_settings()
        use_case = ListPdmUsers(
            session=make_session(gateway, settings),
            settings_repo=FakeAdminSettingsRepository(settings),
            user_repo=FakeUserRepository([]),
            link_repo=FakeUserPdmLinkRepository([]),
        )
        [row] = await use_case.execute(make_user())
        assert row.proposed_user_id is None

    async def test_extended_lookup_failure_is_swallowed_as_no_proposal(self) -> None:
        gateway = FakeGateway(
            users=[PdmUser(id=2, username="jdoe", full_name="Jane Doe")],
            extended_error=PdmApiError("boom", status_code=500, body=""),
        )
        settings = make_pdm_settings()
        use_case = ListPdmUsers(
            session=make_session(gateway, settings),
            settings_repo=FakeAdminSettingsRepository(settings),
            user_repo=FakeUserRepository([]),
            link_repo=FakeUserPdmLinkRepository([]),
        )
        [row] = await use_case.execute(make_user())
        assert row.proposed_user_id is None


# ── LinkPdmUsers ─────────────────────────────────────────────────────


class TestLinkPdmUsers:
    async def test_requires_write_settings_permission(self) -> None:
        gateway = FakeGateway(users=[])
        settings = make_pdm_settings()
        use_case = LinkPdmUsers(
            FakeUserRepository([]),
            FakeUserPdmLinkRepository([]),
            make_session(gateway, settings),
            uow=FakeUnitOfWork(),
        )
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(actor, LinkPdmUsersCommand(links=[]))

    async def test_links_a_user(self) -> None:
        user = make_user(id=5, username="jdoe")
        user_repo = FakeUserRepository([user])
        link_repo = FakeUserPdmLinkRepository([])
        gateway = FakeGateway(users=[PdmUser(id=2, username="jdoe-vault", full_name="Jane Doe")])
        settings = make_pdm_settings()
        await LinkPdmUsers(
            user_repo, link_repo, make_session(gateway, settings), uow=FakeUnitOfWork()
        ).execute(
            make_user(),
            LinkPdmUsersCommand(links=[LinkPdmUserEntryCommand(pdm_user_id=2, user_id=5)]),
        )
        [link] = await link_repo.list_by_user(5)
        assert link.pdm_user_id == 2
        assert link.pdm_username == "jdoe-vault"

    async def test_unlinks_when_user_id_is_none(self) -> None:
        user = make_user(id=5, username="jdoe")
        user_repo = FakeUserRepository([user])
        link_repo = FakeUserPdmLinkRepository(
            [
                UserPdmLink(
                    id=1, user_id=5, pdm_user_id=2, pdm_username="jdoe", linked_at=datetime.now(UTC)
                )
            ]
        )
        gateway = FakeGateway(users=[])
        settings = make_pdm_settings()
        await LinkPdmUsers(
            user_repo, link_repo, make_session(gateway, settings), uow=FakeUnitOfWork()
        ).execute(
            make_user(),
            LinkPdmUsersCommand(links=[LinkPdmUserEntryCommand(pdm_user_id=2, user_id=None)]),
        )
        assert await link_repo.list_by_user(5) == []
        # An unlink-only batch never calls the vault.
        assert await gateway.list_users("tok") == []

    async def test_unknown_user_id_raises_not_found(self) -> None:
        user_repo = FakeUserRepository([])
        link_repo = FakeUserPdmLinkRepository([])
        gateway = FakeGateway(users=[PdmUser(id=2, username="jdoe", full_name="Jane Doe")])
        settings = make_pdm_settings()
        with pytest.raises(UserNotFoundError):
            await LinkPdmUsers(
                user_repo, link_repo, make_session(gateway, settings), uow=FakeUnitOfWork()
            ).execute(
                make_user(),
                LinkPdmUsersCommand(links=[LinkPdmUserEntryCommand(pdm_user_id=2, user_id=999)]),
            )

    async def test_relinking_the_same_pair_is_a_no_op(self) -> None:
        user = make_user(id=5, username="jdoe")
        user_repo = FakeUserRepository([user])
        link_repo = FakeUserPdmLinkRepository(
            [
                UserPdmLink(
                    id=1, user_id=5, pdm_user_id=2, pdm_username="jdoe", linked_at=datetime.now(UTC)
                )
            ]
        )
        gateway = FakeGateway(users=[PdmUser(id=2, username="jdoe", full_name="Jane Doe")])
        settings = make_pdm_settings()
        await LinkPdmUsers(
            user_repo, link_repo, make_session(gateway, settings), uow=FakeUnitOfWork()
        ).execute(
            make_user(),
            LinkPdmUsersCommand(links=[LinkPdmUserEntryCommand(pdm_user_id=2, user_id=5)]),
        )
        [link] = await link_repo.list_by_user(5)
        assert link.pdm_user_id == 2

    async def test_relinking_a_pdm_user_moves_it_from_the_previous_holder(self) -> None:
        old_holder = make_user(id=5, username="jdoe")
        new_holder = make_user(id=6, username="bob")
        user_repo = FakeUserRepository([old_holder, new_holder])
        link_repo = FakeUserPdmLinkRepository(
            [
                UserPdmLink(
                    id=1, user_id=5, pdm_user_id=2, pdm_username="jdoe", linked_at=datetime.now(UTC)
                )
            ]
        )
        gateway = FakeGateway(users=[PdmUser(id=2, username="jdoe", full_name="Jane Doe")])
        settings = make_pdm_settings()
        await LinkPdmUsers(
            user_repo, link_repo, make_session(gateway, settings), uow=FakeUnitOfWork()
        ).execute(
            make_user(),
            LinkPdmUsersCommand(links=[LinkPdmUserEntryCommand(pdm_user_id=2, user_id=6)]),
        )
        assert await link_repo.list_by_user(5) == []
        [link] = await link_repo.list_by_user(6)
        assert link.pdm_user_id == 2

    async def test_linking_a_second_pdm_user_to_the_same_glados_user_is_allowed(self) -> None:
        """Links are one-to-many: a Glados user may hold several PDM users,
        so there is no already-linked-elsewhere rejection."""
        user = make_user(id=5, username="jdoe")
        user_repo = FakeUserRepository([user])
        link_repo = FakeUserPdmLinkRepository(
            [
                UserPdmLink(
                    id=1, user_id=5, pdm_user_id=2, pdm_username="jdoe", linked_at=datetime.now(UTC)
                )
            ]
        )
        gateway = FakeGateway(
            users=[
                PdmUser(id=2, username="jdoe", full_name="Jane Doe"),
                PdmUser(id=3, username="jdoe.alt", full_name="Jane Doe (alt account)"),
            ]
        )
        settings = make_pdm_settings()
        await LinkPdmUsers(
            user_repo, link_repo, make_session(gateway, settings), uow=FakeUnitOfWork()
        ).execute(
            make_user(),
            LinkPdmUsersCommand(links=[LinkPdmUserEntryCommand(pdm_user_id=3, user_id=5)]),
        )
        links = {link.pdm_user_id: link for link in await link_repo.list_by_user(5)}
        assert set(links) == {2, 3}

    async def test_missing_vault_username_falls_back_to_empty_string(self) -> None:
        """A pdm_user_id the current vault listing no longer reports still
        links, rather than failing the whole batch."""
        user = make_user(id=5, username="jdoe")
        user_repo = FakeUserRepository([user])
        link_repo = FakeUserPdmLinkRepository([])
        gateway = FakeGateway(users=[])
        settings = make_pdm_settings()
        await LinkPdmUsers(
            user_repo, link_repo, make_session(gateway, settings), uow=FakeUnitOfWork()
        ).execute(
            make_user(),
            LinkPdmUsersCommand(links=[LinkPdmUserEntryCommand(pdm_user_id=99, user_id=5)]),
        )
        [link] = await link_repo.list_by_user(5)
        assert link.pdm_username == ""
