"""
Unit tests for GetLogEntries.
`GET /api/v1/web/logs/` has no integration test either, so this is the
use case's only coverage: permission gating (read:settings) plus the
thin total/items pass-through from the repository.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.platform.application.use_cases.log.get_log_entries import GetLogEntries
from src.modules.platform.domain.entities.log_entry import LogEntry
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.ports.outbound.repositories.log_repository import LogFilterDto
from tests.factories import make_user

# ── Helpers ───────────────────────────────────────────────────────────


def make_actor(permissions: list[str] | None = None) -> User:
    return make_user(username="admin", full_name="Admin User", permissions=permissions)


def make_entry(id: int = 1, level: str = "HTTP", message: str | None = "ok") -> LogEntry:
    return LogEntry(
        id=id,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        user_id=1,
        username="admin",
        level=level,
        message=message,
        method="GET",
        path="/api/v1/web/users/",
        status_code=200,
        request_id="req-1",
    )


class FakeLogRepository:
    """Records the filters it was called with and returns a fixed page,
    GetLogEntries has no filtering logic of its own to exercise."""

    def __init__(self, total: int, entries: list[LogEntry]) -> None:
        self.total = total
        self.entries = entries
        self.calls: list[LogFilterDto] = []

    async def get_multi(self, filters: LogFilterDto) -> tuple[int, list[LogEntry]]:
        self.calls.append(filters)
        return self.total, self.entries

    async def save(self, entry: LogEntry) -> LogEntry:
        raise NotImplementedError


class TestGetLogEntries:
    async def test_requires_read_settings(self):
        repo = FakeLogRepository(total=0, entries=[])
        use_case = GetLogEntries(repo)

        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(actor=make_actor(permissions=[]), filters=LogFilterDto())

        assert repo.calls == []  # permission checked before any repo access

    async def test_read_settings_holder_gets_the_mapped_page(self):
        entry = make_entry(id=7, message="Something happened")
        repo = FakeLogRepository(total=1, entries=[entry])
        use_case = GetLogEntries(repo)
        filters = LogFilterDto(level="HTTP", skip=0, limit=20)

        total, results = await use_case.execute(
            actor=make_actor([Permission.READ_SETTINGS]), filters=filters
        )

        assert total == 1
        assert len(results) == 1
        assert results[0].id == 7
        assert results[0].message == "Something happened"
        assert results[0].method == "GET"
        # The exact same filters instance was forwarded, unmodified.
        assert repo.calls == [filters]

    async def test_system_user_may_also_read(self):
        """assert_has_permission's system-user exemption applies here too,
        same as every other read:settings/write:settings gate."""
        repo = FakeLogRepository(total=0, entries=[])
        use_case = GetLogEntries(repo)
        system_actor = make_actor(permissions=[])
        system_actor.is_systemuser = True

        total, results = await use_case.execute(actor=system_actor, filters=LogFilterDto())

        assert total == 0
        assert results == []
