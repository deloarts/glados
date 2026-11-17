"""
The reduced user view and the key surface's RFID lookup.

The full user view (e-mail, permissions, groups, 2FA state, last login) is
for user administration, which read:settings opens; everyone else reads the
directory, whose filters never touch the e-mail column. The RFID lookup
answers with a name only and honours the `allow_rfid_login` setting.
"""

from dataclasses import dataclass
from dataclasses import field

import pytest

from src.modules.platform.application.use_cases.user.get_user import GetUser
from src.modules.platform.application.use_cases.user.get_user import GetUserDirectory
from src.modules.platform.application.use_cases.user.get_user import GetUsers
from src.modules.platform.application.use_cases.user.identify_user_by_rfid import IdentifyUserByRfid
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import RfidDisabledError
from src.modules.platform.domain.exceptions import UserNotFoundError
from src.modules.platform.domain.services.user_rules import UserRules
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.security.rfid import rfid_lookup
from src.modules.platform.ports.outbound.repositories.user_repository import UserFilterDto
from tests.factories import make_user


@dataclass
class _UserRepo:
    users: list[User]
    seen_filters: list[UserFilterDto] = field(default_factory=list)

    async def get_by_id(self, id: int) -> User | None:
        return next((u for u in self.users if u.id == id), None)

    async def get_multi(self, filters: UserFilterDto) -> tuple[int, list[User]]:
        self.seen_filters.append(filters)
        return len(self.users), list(self.users)

    async def get_by_rfid(self, rfid: str) -> User | None:
        lookup = rfid_lookup(rfid)
        return next((u for u in self.users if u.rfid_lookup == lookup and u.is_active), None)


class _Links:
    async def list_by_user(self, user_id: int) -> list[object]:
        return []


@dataclass
class _Security:
    allow_rfid_login: bool


class _Settings:
    def __init__(self, *, allow_rfid_login: bool) -> None:
        self._security = _Security(allow_rfid_login=allow_rfid_login)

    async def get_security(self) -> _Security:
        return self._security


PLAIN = make_user(id=1, username="plain")
ADMIN = make_user(id=2, username="admin", permissions=[Permission.READ_SETTINGS])


class TestReadDetailsRule:
    def test_user_administration_reads_anyone(self):
        UserRules.assert_can_read_details(ADMIN, 1)
        UserRules.assert_can_read_details(ADMIN)

    def test_write_settings_reads_anyone_too(self):
        writer = make_user(id=3, username="writer", permissions=[Permission.WRITE_SETTINGS])
        UserRules.assert_can_read_details(writer, 1)

    def test_everyone_reads_their_own_account(self):
        UserRules.assert_can_read_details(PLAIN, PLAIN.id)

    def test_a_plain_user_cannot_read_someone_else(self):
        with pytest.raises(InsufficientPermissionsError):
            UserRules.assert_can_read_details(PLAIN, ADMIN.id)

    def test_a_plain_user_cannot_read_the_full_list(self):
        with pytest.raises(InsufficientPermissionsError):
            UserRules.assert_can_read_details(PLAIN)


class TestFullView:
    async def test_the_full_list_needs_read_settings(self):
        with pytest.raises(InsufficientPermissionsError):
            await GetUsers(_UserRepo([PLAIN, ADMIN]), _Links()).execute(  # type: ignore[arg-type]
                actor=PLAIN, filters=UserFilterDto()
            )

    async def test_someone_elses_details_need_read_settings(self):
        with pytest.raises(InsufficientPermissionsError):
            await GetUser(_UserRepo([PLAIN, ADMIN]), _Links()).execute(  # type: ignore[arg-type]
                actor=PLAIN, user_id=ADMIN.id
            )

    async def test_own_details_need_nothing(self):
        result = await GetUser(_UserRepo([PLAIN]), _Links()).execute(  # type: ignore[arg-type]
            actor=PLAIN, user_id=PLAIN.id
        )
        assert result.email == PLAIN.email


class TestDirectory:
    async def test_items_carry_no_sensitive_field(self):
        repo = _UserRepo([PLAIN, ADMIN])

        page = await GetUserDirectory(repo).execute(UserFilterDto())  # type: ignore[arg-type]

        assert page.total == 2
        fields = set(type(page.items[0]).model_fields)
        assert fields.isdisjoint(
            {"email", "permissions", "direct_permissions", "group_ids", "totp_enabled"}
        )
        assert "last_logged_in" not in fields
        assert {"username", "full_name", "is_active", "has_avatar"} <= fields

    async def test_filters_never_reach_the_email_column(self):
        repo = _UserRepo([PLAIN])

        await GetUserDirectory(repo).execute(  # type: ignore[arg-type]
            UserFilterDto(search="example.com", email="admin@", order_by="email")
        )

        sent = repo.seen_filters[-1]
        assert sent.email is None
        assert sent.search_includes_email is False
        assert sent.order_by is None
        assert sent.search == "example.com"

    async def test_a_name_sort_passes_through(self):
        repo = _UserRepo([PLAIN])

        await GetUserDirectory(repo).execute(UserFilterDto(order_by="full_name"))  # type: ignore[arg-type]

        assert repo.seen_filters[-1].order_by == "full_name"


def _badge_holder(**overrides: object) -> User:
    return make_user(id=7, username="badge", rfid_lookup=rfid_lookup("87654321"), **overrides)


class TestIdentifyUserByRfid:
    async def test_returns_only_the_identity(self):
        use_case = IdentifyUserByRfid(
            _UserRepo([_badge_holder()]),  # type: ignore[arg-type]
            _Settings(allow_rfid_login=True),  # type: ignore[arg-type]
        )

        result = await use_case.execute("87654321")

        assert result.id == 7
        assert set(type(result).model_fields) == {"id", "public_id", "username", "full_name"}

    async def test_disabled_setting_refuses_the_lookup(self):
        use_case = IdentifyUserByRfid(
            _UserRepo([_badge_holder()]),  # type: ignore[arg-type]
            _Settings(allow_rfid_login=False),  # type: ignore[arg-type]
        )

        with pytest.raises(RfidDisabledError):
            await use_case.execute("87654321")

    async def test_unknown_tag_is_not_found(self):
        use_case = IdentifyUserByRfid(
            _UserRepo([_badge_holder()]),  # type: ignore[arg-type]
            _Settings(allow_rfid_login=True),  # type: ignore[arg-type]
        )

        with pytest.raises(UserNotFoundError):
            await use_case.execute("11112222")

    async def test_service_account_is_not_found(self):
        use_case = IdentifyUserByRfid(
            _UserRepo([_badge_holder(is_service_account=True)]),  # type: ignore[arg-type]
            _Settings(allow_rfid_login=True),  # type: ignore[arg-type]
        )

        with pytest.raises(UserNotFoundError):
            await use_case.execute("87654321")
