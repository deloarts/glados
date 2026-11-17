"""
InitDatabase._ensure_system_user creates the `system` account or syncs it
from the config on every startup, and the sync keeps the account's 2FA
enrolment. A second flagged row is refused by the partial unique index on
user_table.is_systemuser, see
tests/integration/test_user_writes_persistence.py.

No database: IUserRepository is a small in-memory fake.
"""

from typing import Any

from src.bootstrap.adapters.outbound.persistence.init_db import InitDatabase
from src.modules.platform.const import SYSTEM_USER
from src.modules.platform.domain.entities.user import User
from tests import factories


def make_user(id: int, username: str, is_systemuser: bool, **overrides: Any) -> User:
    """A user whose stored password is not INIT__PASSWORD, so syncing `system` rehashes it."""
    return factories.make_user(
        id=id, username=username, is_systemuser=is_systemuser, password="x", **overrides
    )


class FakeUserRepo:
    """Just enough of IUserRepository for _ensure_system_user: lookup by
    username and save (upsert by id)."""

    def __init__(self, users: list[User]) -> None:
        self._users: dict[int, User] = {u.id: u for u in users}

    async def get_by_username(self, username: str) -> User | None:
        return next((u for u in self._users.values() if u.username == username), None)

    async def save(self, user: User) -> User:
        self._users[user.id] = user
        return user


class _FakeDb:
    """Only the commit the system-user seeding issues after each save."""

    async def commit(self) -> None:
        pass


def _init_db(repo: FakeUserRepo) -> InitDatabase:
    return InitDatabase(
        user_repo=repo,  # type: ignore[arg-type]
        admin_settings_repo=None,  # type: ignore[arg-type]
        print_template_repo=None,  # type: ignore[arg-type]
        db=_FakeDb(),  # type: ignore[arg-type]
    )


class TestSyncPreservesTotpFields:
    """A restart must not silently un-enrol the account."""

    async def test_totp_secret_and_enabled_survive_the_sync(self):
        system = make_user(
            id=1, username=SYSTEM_USER, is_systemuser=True, totp_secret="s3cr3t", totp_enabled=True
        )
        repo = FakeUserRepo([system])

        await _init_db(repo)._ensure_system_user()

        reloaded = await repo.get_by_username(SYSTEM_USER)
        assert reloaded.totp_secret == "s3cr3t"
        assert reloaded.totp_enabled is True

    async def test_an_unenrolled_system_user_stays_unenrolled(self):
        system = make_user(id=1, username=SYSTEM_USER, is_systemuser=True)
        repo = FakeUserRepo([system])

        await _init_db(repo)._ensure_system_user()

        reloaded = await repo.get_by_username(SYSTEM_USER)
        assert reloaded.totp_secret is None
        assert reloaded.totp_enabled is False
