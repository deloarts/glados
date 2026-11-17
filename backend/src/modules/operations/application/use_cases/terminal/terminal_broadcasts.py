"""
Use cases for messages to terminals. Listing the active messages and
counting how many terminals an audience reaches are open to every signed-in
user, like the terminals list; sending and ending one need
manage:terminals. A message reaches the displays through the live signal of
its own row, after which each display reads its state again. Sending and
ending are written to the audit trail.
"""

from src.modules.operations.application.dto.terminal_broadcast_dto import (
    SendTerminalBroadcastCommand,
)
from src.modules.operations.application.dto.terminal_broadcast_dto import (
    TerminalBroadcastAudienceCommand,
)
from src.modules.operations.application.dto.terminal_broadcast_dto import (
    TerminalBroadcastReachResult,
)
from src.modules.operations.application.dto.terminal_broadcast_dto import TerminalBroadcastResult
from src.modules.operations.application.mappers.terminal_mapper import broadcast_result
from src.modules.operations.application.services.terminal_audit import record_terminal_audit
from src.modules.operations.domain.entities.terminal import Terminal
from src.modules.operations.domain.entities.terminal_broadcast import TerminalBroadcast
from src.modules.operations.domain.errors import TerminalBroadcastNotFoundError
from src.modules.operations.domain.services import terminal_broadcast_rules as rules
from src.modules.operations.domain.services import terminal_rules
from src.modules.operations.domain.value_objects.terminal import TerminalStatus
from src.modules.operations.domain.value_objects.terminal_broadcast import TerminalBroadcastSeverity
from src.modules.operations.domain.value_objects.terminal_broadcast import TerminalBroadcastStyle
from src.modules.operations.ports.outbound.operations_settings_repository import (
    IOperationsSettingsRepository,
)
from src.modules.operations.ports.outbound.repositories.infoscreen_repository import (
    IInfoscreenRepository,
)
from src.modules.operations.ports.outbound.repositories.terminal_broadcast_repository import (
    ITerminalBroadcastRepository,
)
from src.modules.operations.ports.outbound.repositories.terminal_repository import (
    ITerminalRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


def _reach(broadcast: TerminalBroadcast, approved: list[Terminal]) -> int:
    return len(
        rules.reached_terminals(
            all_terminals=broadcast.all_terminals,
            terminal_ids=broadcast.terminal_ids,
            infoscreen_ids=broadcast.infoscreen_ids,
            terminals=approved,
        )
    )


def _audience(broadcast: TerminalBroadcast) -> str:
    if broadcast.all_terminals:
        return "all terminals"
    return (
        f"terminals {list(broadcast.terminal_ids)} and infoscreens {list(broadcast.infoscreen_ids)}"
    )


class ListActiveTerminalBroadcasts:
    def __init__(
        self, broadcast_repo: ITerminalBroadcastRepository, terminal_repo: ITerminalRepository
    ) -> None:
        self._broadcasts = broadcast_repo
        self._terminals = terminal_repo

    async def execute(self) -> list[TerminalBroadcastResult]:
        approved = await self._terminals.get_by_status(TerminalStatus.APPROVED.value)
        return [
            broadcast_result(b, _reach(b, approved))
            for b in await self._broadcasts.get_active(now_utc())
        ]


class CountTerminalBroadcastReach:
    """How many approved terminals a draft audience reaches now."""

    def __init__(self, terminal_repo: ITerminalRepository) -> None:
        self._terminals = terminal_repo

    async def execute(self, cmd: TerminalBroadcastAudienceCommand) -> TerminalBroadcastReachResult:
        approved = await self._terminals.get_by_status(TerminalStatus.APPROVED.value)
        reached = rules.reached_terminals(
            all_terminals=cmd.all_terminals,
            terminal_ids=set(cmd.terminal_ids),
            infoscreen_ids=set(cmd.infoscreen_ids),
            terminals=approved,
        )
        return TerminalBroadcastReachResult(count=len(reached))


class SendTerminalBroadcast:
    def __init__(
        self,
        broadcast_repo: ITerminalBroadcastRepository,
        terminal_repo: ITerminalRepository,
        infoscreen_repo: IInfoscreenRepository,
        settings_repo: IOperationsSettingsRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._broadcasts = broadcast_repo
        self._terminals = terminal_repo
        self._screens = infoscreen_repo
        self._settings = settings_repo
        self._uow = uow

    async def execute(
        self, actor: User, cmd: SendTerminalBroadcastCommand
    ) -> TerminalBroadcastResult:
        terminal_rules.assert_can_manage(actor)
        now = now_utc()
        text = rules.normalise_text(cmd.text)
        rules.assert_display_valid(cmd.severity, cmd.style)
        rules.assert_show_until_valid(cmd.show_until, now)
        terminal_ids = tuple(dict.fromkeys(cmd.terminal_ids))
        infoscreen_ids = tuple(dict.fromkeys(cmd.infoscreen_ids))
        terminals = await self._terminals.get_all()
        rules.assert_audience_valid(
            all_terminals=cmd.all_terminals,
            terminal_ids=terminal_ids,
            infoscreen_ids=infoscreen_ids,
            known_terminal_ids={t.id for t in terminals},
            known_infoscreen_ids={s.id for s in await self._screens.get_all(include_archived=True)},
        )
        saved = await self._broadcasts.save(
            TerminalBroadcast(
                id=0,
                created=now,
                changed=now,
                text=text,
                severity=TerminalBroadcastSeverity(cmd.severity),
                style=TerminalBroadcastStyle(cmd.style),
                show_until=cmd.show_until,
                all_terminals=cmd.all_terminals,
                created_by_id=actor.id,
                terminal_ids=terminal_ids,
                infoscreen_ids=infoscreen_ids,
            )
        )
        await record_terminal_audit(
            self._settings,
            actor,
            f"Sent message #{saved.id} to {_audience(saved)} until "
            f"{saved.show_until.isoformat()} by {actor.username}.",
        )
        await self._uow.commit()
        log.info(f"Sent message #{saved.id} to {_audience(saved)}.")
        approved = [t for t in terminals if t.status == TerminalStatus.APPROVED.value]
        return broadcast_result(saved, _reach(saved, approved))


class EndTerminalBroadcast:
    """Ends a message now; ending one that already ended changes nothing."""

    def __init__(
        self,
        broadcast_repo: ITerminalBroadcastRepository,
        terminal_repo: ITerminalRepository,
        settings_repo: IOperationsSettingsRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._broadcasts = broadcast_repo
        self._terminals = terminal_repo
        self._settings = settings_repo
        self._uow = uow

    async def execute(self, actor: User, broadcast_id: int) -> TerminalBroadcastResult:
        terminal_rules.assert_can_manage(actor)
        broadcast = found_or_raise(
            await self._broadcasts.get_by_id(broadcast_id),
            TerminalBroadcastNotFoundError,
            f"Message #{broadcast_id} not found.",
        )
        if rules.end(broadcast, now_utc()):
            broadcast = await self._broadcasts.save(broadcast)
            await record_terminal_audit(
                self._settings, actor, f"Ended message #{broadcast.id} by {actor.username}."
            )
            await self._uow.commit()
            log.info(f"Ended message #{broadcast.id}.")
        approved = await self._terminals.get_by_status(TerminalStatus.APPROVED.value)
        return broadcast_result(broadcast, _reach(broadcast, approved))
