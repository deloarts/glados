"""Actions on all terminals in one unit of work, and the live signal of
messages to terminals: only approved displays and web users receive it."""

from datetime import UTC
from datetime import datetime
from typing import Any

import pytest

from src.modules.operations.application.use_cases.terminal.terminal_bulk import RevokeAllTerminals
from src.modules.operations.domain.entities.terminal import Terminal
from src.modules.operations.domain.value_objects.terminal import TerminalMode
from src.modules.operations.domain.value_objects.terminal import TerminalStatus
from src.modules.platform.adapters.inbound.api.live.hub import LiveHub
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.ports.outbound.live_signal import LiveResource
from src.modules.platform.ports.outbound.live_signal import LiveSignal
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork

NOW = datetime(2026, 11, 3, 12, tzinfo=UTC)


def _terminal(id: int, status: TerminalStatus) -> Terminal:
    return Terminal(
        id=id,
        public_key=f"k{id}",
        public_key_fingerprint="0123456789abcdef",
        status=status,
        mode=TerminalMode.INFOSCREEN,
        name=f"T{id}",
        pairing_code=None,
        pairing_expires_at=None,
        infoscreen_id=None,
        api_key_id=None,
        first_seen_at=NOW,
        last_seen_at=NOW,
    )


class _Terminals:
    """Saves approved terminals until the save named by `fail_on` raises."""

    def __init__(self, fail_on: int | None = None) -> None:
        self.terminals = [
            _terminal(1, TerminalStatus.APPROVED),
            _terminal(2, TerminalStatus.APPROVED),
            _terminal(3, TerminalStatus.PENDING),
        ]
        self.saved: list[int] = []
        self._fail_on = fail_on

    async def get_by_status(self, status: str) -> list[Terminal]:
        return [t for t in self.terminals if t.status == status]

    async def lock_for_update(self, id: int) -> Terminal | None:
        return next((t for t in self.terminals if t.id == id), None)

    async def save(self, terminal: Terminal) -> Terminal:
        if terminal.id == self._fail_on:
            raise RuntimeError("database gone")
        self.saved.append(terminal.id)
        return terminal


class _Settings:
    def __init__(self) -> None:
        self.audit: list[Any] = []

    async def append_audit(self, entry: Any) -> None:
        self.audit.append(entry)


def _manager() -> Any:
    return make_user(permissions=[Permission.MANAGE_TERMINALS])


async def test_terminal_bulk_revoke_touches_approved_terminals_and_commits_once() -> None:
    repo, settings, uow = _Terminals(), _Settings(), FakeUnitOfWork()
    result = await RevokeAllTerminals(repo, settings, uow=uow).execute(_manager())  # type: ignore[arg-type]
    assert result.count == 2
    assert repo.saved == [1, 2]
    assert uow.commits == 1
    assert len(settings.audit) == 1


async def test_terminal_bulk_failure_commits_nothing() -> None:
    repo, settings, uow = _Terminals(fail_on=2), _Settings(), FakeUnitOfWork()
    with pytest.raises(RuntimeError):
        await RevokeAllTerminals(repo, settings, uow=uow).execute(_manager())  # type: ignore[arg-type]
    assert uow.commits == 0


async def test_terminal_bulk_needs_manage_terminals() -> None:
    repo, uow = _Terminals(), FakeUnitOfWork()
    with pytest.raises(InsufficientPermissionsError):
        await RevokeAllTerminals(repo, _Settings(), uow=uow).execute(make_user(permissions=[]))  # type: ignore[arg-type]
    assert repo.saved == []


def _broadcast_signal() -> LiveSignal:
    return LiveSignal(
        resource=LiveResource.TERMINAL_BROADCASTS, id=5, action="created", actor_id=None
    )


def test_terminal_broadcast_signal_reaches_approved_displays_and_web_users() -> None:
    hub = LiveHub()
    approved = hub.connect_terminal(7, approved=True, infoscreen_id=None)
    pending = hub.connect_terminal(8, approved=False, infoscreen_id=None)
    user = hub.connect(1)
    hub.broadcast([_broadcast_signal()])
    assert approved.queue.get_nowait() == [_broadcast_signal()]
    assert pending.queue.empty()
    assert user.queue.get_nowait() == [_broadcast_signal()]
