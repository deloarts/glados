"""
Repository interface for messages to terminals.
"""

from datetime import datetime
from typing import Protocol
from typing import runtime_checkable

from src.modules.operations.domain.entities.terminal_broadcast import TerminalBroadcast


@runtime_checkable
class ITerminalBroadcastRepository(Protocol):
    async def get_by_id(self, id: int) -> TerminalBroadcast | None: ...

    async def get_active(self, now: datetime) -> list[TerminalBroadcast]:
        """The messages not ended and still shown at `now`, newest first."""
        ...

    async def save(self, broadcast: TerminalBroadcast) -> TerminalBroadcast:
        """Inserts a new message with its picks, or updates an existing
        one's end. The picks of an existing message never change."""
        ...
