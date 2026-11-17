"""
Unit tests for ForceLogoutUser and ForceLogoutAllUsers.

tests/integration/test_api_sessions.py already exercises `DELETE
/users/me/session` end to end, which is ForceLogoutUser called with
target == actor (the self-logout path); that HTTP-level coverage is not
duplicated here. What is missing, and what this file covers, is the branch
that self-logout never reaches: an admin force-logging out *someone else*
(permission gate, system-user protection, the event published, and that
every one of PAT/session/trusted-device revocation actually gets called),
plus ForceLogoutAllUsers, whose route (`DELETE /users/sessions`) has no
test at any level.

Fakes are imported from the sibling user/pat test modules rather than
redefined, matching this repo's existing convention of one canonical fake
per repository interface.
"""

import pytest

from src.modules.platform.application.use_cases.user.force_logout_all_users import (
    ForceLogoutAllUsers,
)
from src.modules.platform.application.use_cases.user.force_logout_user import ForceLogoutUser
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import SystemUserProtectedError
from src.modules.platform.domain.exceptions import UserNotFoundError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.ports.outbound.repositories.user_repository import UserFilterDto
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.test_pat_use_cases import FakePatRepository
from tests.unit.test_user_use_cases import FakeEventBus
from tests.unit.test_user_use_cases import FakeTrustedDeviceRepository
from tests.unit.test_user_use_cases import FakeUserPdmLinkRepository
from tests.unit.test_user_use_cases import FakeUserRepository
from tests.unit.test_user_use_cases import FakeUserSessionRepository


class FakeUserRepositoryHonoringIsActive(FakeUserRepository):
    """FakeUserRepository (imported above) ignores every UserFilterDto
    field but skip/limit, fine for the pagination-shaped tests it was
    written for, but ForceLogoutAllUsers depends on `get_multi(is_active=
    True)` actually filtering, the way the real SQLAlchemy repository
    does. This subclass adds only that."""

    async def get_multi(self, filters: UserFilterDto) -> tuple[int, list[User]]:
        users = list(self._users.values())
        if filters.is_active is not None:
            users = [u for u in users if u.is_active == filters.is_active]
        return len(users), users


def make_force_logout_user(users, pats=None, sessions=None, devices=None, links=None, bus=None):
    return ForceLogoutUser(
        user_repo=users,
        pat_repo=pats or FakePatRepository(),
        session_repo=sessions or FakeUserSessionRepository(),
        trusted_device_repo=devices or FakeTrustedDeviceRepository(),
        link_repo=links or FakeUserPdmLinkRepository(),
        event_bus=bus or FakeEventBus(),
        uow=FakeUnitOfWork(),
    )


class TestForceLogoutUserOnSomeoneElse:
    async def test_requires_write_settings(self):
        admin = make_user(id=1, permissions=[])
        target = make_user(id=2)
        users = FakeUserRepository([admin, target])
        use_case = make_force_logout_user(users)

        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(actor=admin, target_id=target.id)

        # Nothing was touched.
        assert target.token_version == 0

    async def test_write_settings_holder_revokes_pats_sessions_and_devices(self):
        admin = make_user(id=1, permissions=[Permission.WRITE_SETTINGS])
        target = make_user(id=2)
        users = FakeUserRepository([admin, target])
        pats = FakePatRepository()
        sessions = FakeUserSessionRepository()
        devices = FakeTrustedDeviceRepository()
        bus = FakeEventBus()
        use_case = make_force_logout_user(
            users, pats=pats, sessions=sessions, devices=devices, bus=bus
        )
        original_version = target.token_version

        await use_case.execute(actor=admin, target_id=target.id)

        assert target.token_version == original_version + 1
        assert sessions.revoked_except == [(target.id, None)]
        assert devices.revoked_for == [target.id]
        assert len(bus.published) == 1
        assert bus.published[0].user_id == target.id
        assert bus.published[0].actor_id == admin.id

    async def test_system_user_cannot_be_force_logged_out(self):
        admin = make_user(id=1, permissions=[Permission.WRITE_SETTINGS])
        system_user = make_user(id=2, is_systemuser=True)
        users = FakeUserRepository([admin, system_user])
        use_case = make_force_logout_user(users)

        with pytest.raises(SystemUserProtectedError):
            await use_case.execute(actor=admin, target_id=system_user.id)

    async def test_unknown_target_is_not_found(self):
        admin = make_user(id=1, permissions=[Permission.WRITE_SETTINGS])
        users = FakeUserRepository([admin])
        use_case = make_force_logout_user(users)

        with pytest.raises(UserNotFoundError):
            await use_case.execute(actor=admin, target_id=999)

    async def test_a_user_may_always_force_logout_themselves_without_write_settings(self):
        """Self-logout's actual HTTP round trip is covered by
        test_api_sessions.py; this pins the permission-rule branch that
        makes it possible with no write:settings at all."""
        user = make_user(id=1, permissions=[])
        users = FakeUserRepository([user])
        use_case = make_force_logout_user(users)

        result = await use_case.execute(actor=user, target_id=user.id)

        assert result.id == user.id
        assert user.token_version == 1


class TestForceLogoutAllUsers:
    async def test_requires_write_settings(self):
        admin = make_user(id=1, permissions=[])
        users = FakeUserRepository([admin])
        use_case = ForceLogoutAllUsers(
            user_repo=users,
            pat_repo=FakePatRepository(),
            session_repo=FakeUserSessionRepository(),
            trusted_device_repo=FakeTrustedDeviceRepository(),
            uow=FakeUnitOfWork(),
        )

        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(actor=admin)

    async def test_logs_out_every_active_non_system_user_except_the_actor(self):
        admin = make_user(id=1, username="admin", permissions=[Permission.WRITE_SETTINGS])
        other_active = make_user(id=2, username="other")
        inactive = make_user(id=3, username="inactive", is_active=False)
        system_user = make_user(id=4, username="system", is_systemuser=True)
        users = FakeUserRepositoryHonoringIsActive([admin, other_active, inactive, system_user])
        sessions = FakeUserSessionRepository()
        devices = FakeTrustedDeviceRepository()
        use_case = ForceLogoutAllUsers(
            user_repo=users,
            pat_repo=FakePatRepository(),
            session_repo=sessions,
            trusted_device_repo=devices,
            uow=FakeUnitOfWork(),
        )

        count = await use_case.execute(actor=admin)

        # inactive is excluded by the get_multi(is_active=True) filter, the
        # system user and the actor themselves are excluded explicitly.
        assert count == 1
        assert other_active.token_version == 1
        assert admin.token_version == 0
        assert system_user.token_version == 0
        assert sessions.revoked_except == [(other_active.id, None)]
        assert devices.revoked_for == [other_active.id]

    async def test_no_other_active_users_logs_out_nobody(self):
        admin = make_user(id=1, permissions=[Permission.WRITE_SETTINGS])
        users = FakeUserRepository([admin])
        use_case = ForceLogoutAllUsers(
            user_repo=users,
            pat_repo=FakePatRepository(),
            session_repo=FakeUserSessionRepository(),
            trusted_device_repo=FakeTrustedDeviceRepository(),
            uow=FakeUnitOfWork(),
        )

        count = await use_case.execute(actor=admin)

        assert count == 0
