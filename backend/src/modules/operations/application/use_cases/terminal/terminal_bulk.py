"""
Actions on all terminals at once, each one request and one unit of work:
reload, identify and revoke every approved terminal, and delete every
terminal, waiting and revoked ones included. Each needs manage:terminals
and answers how many terminals it touched. Nothing is committed until every
terminal is done, so a failure leaves all of them as they were. Every
touched row is signalled to the live stream as a single action would be.
Revoking and deleting all are written to the audit trail once.
"""

from collections.abc import Callable
from datetime import datetime

from src.modules.operations.application.dto.terminal_dto import TerminalBulkResult
from src.modules.operations.application.services.terminal_audit import record_terminal_audit
from src.modules.operations.domain.entities.terminal import Terminal
from src.modules.operations.domain.services import terminal_rules
from src.modules.operations.domain.value_objects.terminal import TerminalStatus
from src.modules.operations.ports.outbound.operations_settings_repository import (
    IOperationsSettingsRepository,
)
from src.modules.operations.ports.outbound.repositories.terminal_repository import (
    ITerminalRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc

_APPROVED = TerminalStatus.APPROVED.value


def _ids(terminals: list[Terminal]) -> str:
    return ", ".join(f"#{t.id}" for t in terminals) or "none"


class _TerminalBulk:
    def __init__(
        self,
        terminal_repo: ITerminalRepository,
        settings_repo: IOperationsSettingsRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._terminals = terminal_repo
        self._settings = settings_repo
        self._uow = uow

    async def _update_approved(
        self, change: Callable[[Terminal, datetime], None]
    ) -> list[Terminal]:
        now = now_utc()
        touched: list[Terminal] = []
        for candidate in await self._terminals.get_by_status(_APPROVED):
            # Locked and read again, so a terminal whose status changed
            # since the list was read is left alone and the change lands on
            # the current row.
            terminal = await self._terminals.lock_for_update(candidate.id)
            if terminal is None or terminal.status != _APPROVED:
                continue
            change(terminal, now)
            terminal.changed = now
            await self._terminals.save(terminal)
            touched.append(terminal)
        return touched


def _request_reload(terminal: Terminal, now: datetime) -> None:
    terminal.reload_requested_at = now


def _request_identify(terminal: Terminal, now: datetime) -> None:
    terminal.identify_requested_at = now


class ReloadAllTerminals(_TerminalBulk):
    async def execute(self, actor: User) -> TerminalBulkResult:
        terminal_rules.assert_can_manage(actor)
        touched = await self._update_approved(_request_reload)
        await self._uow.commit()
        log.info(f"Requested a reload of {len(touched)} approved terminal(s).")
        return TerminalBulkResult(count=len(touched))


class IdentifyAllTerminals(_TerminalBulk):
    async def execute(self, actor: User) -> TerminalBulkResult:
        terminal_rules.assert_can_manage(actor)
        touched = await self._update_approved(_request_identify)
        await self._uow.commit()
        log.info(f"Requested {len(touched)} approved terminal(s) to identify themselves.")
        return TerminalBulkResult(count=len(touched))


class RevokeAllTerminals(_TerminalBulk):
    async def execute(self, actor: User) -> TerminalBulkResult:
        terminal_rules.assert_can_manage(actor)
        touched = await self._update_approved(terminal_rules.revoke)
        await record_terminal_audit(
            self._settings,
            actor,
            f"Revoked all {len(touched)} approved terminal(s) ({_ids(touched)}) by "
            f"{actor.username}.",
        )
        await self._uow.commit()
        log.info(f"Revoked all {len(touched)} approved terminal(s): {_ids(touched)}.")
        return TerminalBulkResult(count=len(touched))


class DeleteAllTerminals(_TerminalBulk):
    """Removes every terminal. Their next sign-ins count as unknown devices
    and need a terminal key again."""

    async def execute(self, actor: User) -> TerminalBulkResult:
        terminal_rules.assert_can_manage(actor)
        terminals = await self._terminals.get_all()
        for terminal in terminals:
            await self._terminals.delete(terminal)
        await record_terminal_audit(
            self._settings,
            actor,
            f"Deleted all {len(terminals)} terminal(s) ({_ids(terminals)}) by {actor.username}.",
        )
        await self._uow.commit()
        log.info(f"Deleted all {len(terminals)} terminal(s): {_ids(terminals)}.")
        return TerminalBulkResult(count=len(terminals))
