"""
Race tests of the terminal writes. A device request reads its terminal
before an admin's revoke or approval commits and finishes afterwards. Writing
the whole terminal back from that early read would undo the admin's change,
so the sign-in re-reads a known terminal under its row lock and the access
check writes only the two telemetry columns. Each test holds the device side
right after its read, lets the admin side commit, then lets the device side
go on, and reads the row back on a fresh session.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncEngine

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.operations.adapters.inbound.api.deps import terminals as terminal_deps
from src.modules.operations.adapters.inbound.api.deps.repositories import (
    get_operations_settings_repo,
)
from src.modules.operations.adapters.inbound.api.deps.repositories import get_terminal_repo
from src.modules.operations.adapters.outbound.persistence.repositories.terminal_repository import (
    SqlAlchemyTerminalRepository,
)
from src.modules.operations.application.dto.terminal_dto import ApproveTerminalCommand
from src.modules.operations.application.dto.terminal_dto import StartTerminalSessionCommand
from src.modules.operations.application.use_cases.terminal_device.authenticate_terminal import (
    AuthenticateTerminal,
)
from src.modules.operations.domain.entities.terminal import Terminal
from src.modules.operations.domain.value_objects.terminal import TerminalMode
from src.modules.operations.domain.value_objects.terminal import TerminalStatus
from src.modules.operations.infrastructure.security.terminal_auth import (
    create_terminal_access_token,
)
from src.modules.operations.infrastructure.security.terminal_auth import issue_nonce
from src.modules.operations.ports.outbound.operations_settings_repository import (
    IOperationsSettingsRepository,
)
from src.modules.operations.ports.outbound.repositories.terminal_repository import (
    ITerminalRepository,
)
from src.modules.platform.adapters.inbound.api.deps.bindings import (
    get_schedule_recompute_generation_counter,
)
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.adapters.inbound.api.deps.services import get_replay_guard
from src.modules.platform.domain.entities.admin_settings.maintenance import AdminMaintenanceSettings
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc
from tests.integration._terminal_helpers import Device
from tests.integration._terminal_helpers import seed_security
from tests.pg._floor import Floor
from tests.pg._race import SIDE
from tests.pg._race import Gate
from tests.pg._race import LocalGenerationCounter
from tests.pg._race import request
from tests.pg._race import sessions
from tests.pg._race import start
from tests.pg._wiring import build

DEVICE_IP = "10.0.0.7"
PAIRING_CODE = "ABC234"


class _OpenReplayGuard:
    """A replay guard that accepts every nonce, standing in for Redis."""

    async def consume_once(self, key: str, ttl_seconds: int) -> bool:
        return True


def _authenticate(
    terminal_repo: ITerminalRepository = Depends(get_terminal_repo),
    settings_repo: IOperationsSettingsRepository = Depends(get_operations_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> AuthenticateTerminal:
    """The use case the device bearer dependency builds, as a factory."""
    return AuthenticateTerminal(terminal_repo=terminal_repo, settings_repo=settings_repo, uow=uow)


async def _device_request[R](
    engine: AsyncEngine,
    factory: Callable[..., Any],
    call: Callable[[Any], Awaitable[R]],
) -> R:
    """Runs `call` as the device side on its own session, with the replay
    guard replaced by an open one."""
    SIDE.set("a")
    async with sessions(engine)() as db:
        use_case = await build(
            factory,
            db,
            {
                get_schedule_recompute_generation_counter: LocalGenerationCounter(),
                get_replay_guard: _OpenReplayGuard(),
            },
        )
        try:
            return await call(use_case)
        except BaseException:
            await db.rollback()
            raise


async def _seed_terminal(floor: Floor, device: Device, *, approved: bool) -> int:
    """A terminal of `device` whose last contact is long past, so the access
    check has a telemetry write to make; approved, or pending with a live
    pairing code."""
    await seed_security(floor.db)
    await SqlAlchemyAdminSettingsRepository(floor.db).save_maintenance(
        AdminMaintenanceSettings(id=1, enabled=False, message=None)
    )
    await floor.db.commit()
    now = now_utc()
    long_ago = now - timedelta(hours=1)
    terminal = Terminal(
        id=0,
        public_key=device.public_key,
        public_key_fingerprint="0123456789abcdef",
        status=TerminalStatus.APPROVED if approved else TerminalStatus.PENDING,
        mode=TerminalMode.default(),
        name="Hall 2" if approved else None,
        pairing_code=None if approved else PAIRING_CODE,
        pairing_expires_at=None if approved else now + timedelta(minutes=30),
        infoscreen_id=None,
        api_key_id=None,
        first_seen_at=long_ago,
        last_seen_at=long_ago,
        last_ip="10.0.0.1",
        approved_at=long_ago if approved else None,
        approved_by_id=floor.actor.id if approved else None,
        created=long_ago,
    )
    saved = await SqlAlchemyTerminalRepository(floor.db).save(terminal)
    await floor.db.commit()
    return saved.id


async def _read(engine: AsyncEngine, terminal_id: int) -> Terminal:
    """The terminal as a fresh session reads it."""
    async with sessions(engine)() as db:
        terminal = await SqlAlchemyTerminalRepository(db).get_by_id(terminal_id)
    assert terminal is not None
    return terminal


def _terminal_token(terminal_id: int) -> str:
    token, _ = create_terminal_access_token(terminal_id, now_utc(), timedelta(minutes=5))
    return token


def _hold_device_after_read(monkeypatch: Any, method: str) -> Gate:
    """Stops the device side right after its first call of the repository's
    `method`, which is its read of the terminal."""
    gate = Gate("a")
    monkeypatch.setattr(
        SqlAlchemyTerminalRepository,
        method,
        gate.wrap(getattr(SqlAlchemyTerminalRepository, method), after=True),
    )
    return gate


async def test_a_revoke_committed_during_an_access_check_is_not_undone(
    floor: Floor, engine_a: AsyncEngine, engine_b: AsyncEngine, monkeypatch: Any
) -> None:
    device = Device()
    terminal_id = await _seed_terminal(floor, device, approved=True)
    gate = _hold_device_after_read(monkeypatch, "get_by_id")
    token_of_terminal = _terminal_token(terminal_id)

    check = start(
        _device_request(
            engine_a, _authenticate, lambda use_case: use_case.execute(token_of_terminal, DEVICE_IP)
        )
    )
    await gate.wait_reached()

    await request(
        "b",
        engine_b,
        terminal_deps.get_revoke_terminal_use_case,
        lambda use_case: use_case.execute(floor.actor, terminal_id),
    )
    gate.release()
    await check

    terminal = await _read(engine_b, terminal_id)
    assert terminal.status == TerminalStatus.REVOKED
    assert terminal.revoked_at is not None
    # The access check's own telemetry write still happened.
    assert terminal.last_ip == DEVICE_IP


async def test_an_approval_committed_during_an_access_check_is_not_undone(
    floor: Floor, engine_a: AsyncEngine, engine_b: AsyncEngine, monkeypatch: Any
) -> None:
    device = Device()
    terminal_id = await _seed_terminal(floor, device, approved=False)
    gate = _hold_device_after_read(monkeypatch, "get_by_id")
    token_of_terminal = _terminal_token(terminal_id)

    check = start(
        _device_request(
            engine_a, _authenticate, lambda use_case: use_case.execute(token_of_terminal, DEVICE_IP)
        )
    )
    await gate.wait_reached()

    await request(
        "b",
        engine_b,
        terminal_deps.get_approve_terminal_use_case,
        lambda use_case: use_case.execute(
            floor.actor,
            terminal_id,
            ApproveTerminalCommand(pairing_code=PAIRING_CODE, name="Hall 2"),
        ),
    )
    gate.release()
    await check

    terminal = await _read(engine_b, terminal_id)
    assert terminal.status == TerminalStatus.APPROVED
    assert terminal.approved_at is not None
    assert terminal.last_ip == DEVICE_IP


async def test_a_revoke_committed_during_a_sign_in_sends_the_display_back_to_pending(
    floor: Floor, engine_a: AsyncEngine, engine_b: AsyncEngine, monkeypatch: Any
) -> None:
    device = Device()
    terminal_id = await _seed_terminal(floor, device, approved=True)
    gate = _hold_device_after_read(monkeypatch, "get_by_public_key")
    nonce, _ = issue_nonce(device.public_key, now_utc(), 60)
    command = StartTerminalSessionCommand(**device.session_body(nonce), client_ip=DEVICE_IP)

    sign_in = start(
        _device_request(
            engine_a,
            terminal_deps.get_start_terminal_session_use_case,
            lambda use_case: use_case.execute(command),
        )
    )
    await gate.wait_reached()

    await request(
        "b",
        engine_b,
        terminal_deps.get_revoke_terminal_use_case,
        lambda use_case: use_case.execute(floor.actor, terminal_id),
    )
    gate.release()
    await sign_in

    # The sign-in saw the committed revoke, so the documented path applies:
    # a revoked display that signs in again waits for a new approval.
    terminal = await _read(engine_b, terminal_id)
    assert terminal.status == TerminalStatus.PENDING
    assert terminal.approved_at is None
    assert terminal.revoked_at is not None
    assert terminal.pairing_code is not None
