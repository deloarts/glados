"""
What a terminal's live stream may carry right now: whether the terminal is
approved and which screen it shows. Read again whenever the terminal's own
row changes, since an admin can approve, revoke or reassign it at any time.
None means the terminal is gone and its stream ends.
"""

from dataclasses import dataclass

from src.modules.operations.domain.value_objects.terminal import TerminalStatus
from src.modules.operations.ports.outbound.repositories.terminal_repository import (
    ITerminalRepository,
)


@dataclass(frozen=True)
class TerminalLiveScope:
    approved: bool
    infoscreen_id: int | None


class GetTerminalLiveScope:
    def __init__(self, terminal_repo: ITerminalRepository) -> None:
        self._terminals = terminal_repo

    async def execute(self, terminal_id: int) -> TerminalLiveScope | None:
        terminal = await self._terminals.get_by_id(terminal_id)
        if terminal is None:
            return None
        return TerminalLiveScope(
            approved=terminal.status == TerminalStatus.APPROVED.value,
            infoscreen_id=terminal.infoscreen_id,
        )
