"""
How user administration treats stored time tracking credentials: turning
an account that holds them into a shared or service account is refused
until they are removed, deactivation (by update or by delete) removes them,
and the administrative removal needs write:settings for anyone but oneself.
"""

import pytest

from src.modules.operations.application.use_cases.time_tracking.delete_user_time_tracking_credentials import (
    DeleteUserTimeTrackingCredentials,
)
from src.modules.platform.application.dto.user_dto import UpdateUserCommand
from src.modules.platform.application.use_cases.user.delete_user import DeleteUser
from src.modules.platform.application.use_cases.user.update_user import UpdateUser
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import TimeTrackingCredentialsNotAllowedError
from src.modules.platform.domain.exceptions import UserNotFoundError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.unit.fakes import FakeEventBus
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.time_tracking._helpers import make_credentials
from tests.unit.time_tracking._helpers import make_user
from tests.unit.time_tracking.fakes import FakeCredentialsRepo


class FakeUsers:
    def __init__(self, *users: User) -> None:
        self.users = {u.id: u for u in users}

    async def get_by_id(self, id: int) -> User | None:
        return self.users.get(id)

    async def get_by_username(self, username: str) -> User | None:
        return next((u for u in self.users.values() if u.username == username), None)

    async def get_by_email(self, email: str) -> User | None:
        return next((u for u in self.users.values() if u.email == email), None)

    async def save(self, user: User) -> User:
        self.users[user.id] = user
        return user


class Revocations:
    async def revoke_all_for_user_except(self, user_id: int, keep: object) -> int:
        return 0

    async def revoke_all_for_user(self, user_id: int) -> int:
        return 0


class NoLinks:
    async def list_by_user(self, user_id: int) -> list[object]:
        return []


async def _hash(value: str) -> str:
    return f"hashed:{value}"


ADMIN = make_user(id=1, username="admin", permissions=[Permission.WRITE_SETTINGS])


def update_user(users: FakeUsers, credentials: FakeCredentialsRepo) -> UpdateUser:
    return UpdateUser(
        user_repo=users,  # type: ignore[arg-type]
        min_password_length=8,
        hash_fn=_hash,
        session_repo=Revocations(),  # type: ignore[arg-type]
        trusted_device_repo=Revocations(),  # type: ignore[arg-type]
        link_repo=NoLinks(),  # type: ignore[arg-type]
        event_bus=FakeEventBus(),
        uow=FakeUnitOfWork(),
        time_tracking_credentials_repo=credentials,  # type: ignore[arg-type]
    )


async def test_turning_a_user_with_credentials_into_a_shared_account_is_refused() -> None:
    target = make_user()
    users = FakeUsers(ADMIN, target)
    credentials = FakeCredentialsRepo(make_credentials(user_id=target.id))

    with pytest.raises(TimeTrackingCredentialsNotAllowedError, match="Remove"):
        await update_user(users, credentials).execute(
            ADMIN, target.id, UpdateUserCommand(is_shared_account=True)
        )


async def test_conversion_is_allowed_once_the_credentials_are_removed() -> None:
    target = make_user()
    users = FakeUsers(ADMIN, target)
    credentials = FakeCredentialsRepo(make_credentials(user_id=target.id))
    await DeleteUserTimeTrackingCredentials(users, credentials, uow=FakeUnitOfWork()).execute(  # type: ignore[arg-type]
        ADMIN, target.id
    )

    result = await update_user(users, credentials).execute(
        ADMIN, target.id, UpdateUserCommand(is_shared_account=True)
    )

    assert result.is_shared_account


async def test_other_updates_of_a_user_with_credentials_are_unaffected() -> None:
    target = make_user()
    users = FakeUsers(ADMIN, target)
    credentials = FakeCredentialsRepo(make_credentials(user_id=target.id))

    result = await update_user(users, credentials).execute(
        ADMIN, target.id, UpdateUserCommand(full_name="Jane Q. Doe")
    )

    assert result.full_name == "Jane Q. Doe"
    assert target.id in credentials.rows


async def test_deactivation_by_update_deletes_the_credentials() -> None:
    target = make_user()
    users = FakeUsers(ADMIN, target)
    credentials = FakeCredentialsRepo(make_credentials(user_id=target.id))

    await update_user(users, credentials).execute(
        ADMIN, target.id, UpdateUserCommand(is_active=False)
    )

    assert target.id not in credentials.rows


async def test_deactivation_by_delete_deletes_the_credentials() -> None:
    target = make_user()
    users = FakeUsers(ADMIN, target)
    credentials = FakeCredentialsRepo(make_credentials(user_id=target.id))

    await DeleteUser(
        users,  # type: ignore[arg-type]
        NoLinks(),  # type: ignore[arg-type]
        uow=FakeUnitOfWork(),
        time_tracking_credentials_repo=credentials,  # type: ignore[arg-type]
    ).execute(ADMIN, target.id)

    assert target.id not in credentials.rows


async def test_removing_another_users_credentials_needs_write_settings() -> None:
    target = make_user()
    stranger = make_user(id=9, username="other")
    users = FakeUsers(target, stranger)
    credentials = FakeCredentialsRepo(make_credentials(user_id=target.id))
    use_case = DeleteUserTimeTrackingCredentials(users, credentials, uow=FakeUnitOfWork())  # type: ignore[arg-type]

    with pytest.raises(InsufficientPermissionsError):
        await use_case.execute(stranger, target.id)
    assert target.id in credentials.rows

    await use_case.execute(target, target.id)
    assert target.id not in credentials.rows


async def test_removing_credentials_of_an_unknown_user_is_not_found() -> None:
    use_case = DeleteUserTimeTrackingCredentials(
        FakeUsers(ADMIN),  # type: ignore[arg-type]
        FakeCredentialsRepo(),  # type: ignore[arg-type]
        uow=FakeUnitOfWork(),
    )

    with pytest.raises(UserNotFoundError):
        await use_case.execute(ADMIN, 404)
