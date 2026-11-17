"""
Repository interface for terminals.
"""

from datetime import datetime
from typing import Protocol
from typing import runtime_checkable

from src.modules.operations.domain.entities.terminal import Terminal


@runtime_checkable
class ITerminalRepository(Protocol):
    async def get_by_id(self, id: int) -> Terminal | None: ...

    async def lock_for_update(self, id: int) -> Terminal | None:
        """Locks the terminal's row until the transaction ends and returns
        it as stored now, so a status change is made to the current row and
        no concurrent device request can write an older status over it."""
        ...

    async def touch_seen(self, id: int, seen_at: datetime, ip: str | None) -> None:
        """Records when and from where the device was last seen, and nothing
        else, so a status an admin changed meanwhile stays as it is."""
        ...

    async def get_by_public_key(self, public_key: str) -> Terminal | None: ...

    async def get_visible(self, now: datetime) -> list[Terminal]:
        """Every terminal except pending ones whose pairing code has expired,
        ordered by id."""
        ...

    async def get_all(self) -> list[Terminal]:
        """Every terminal, expired pending ones included, ordered by id."""
        ...

    async def get_by_status(self, status: str) -> list[Terminal]:
        """The terminals with this status, ordered by id."""
        ...

    async def count_active_pending(self, now: datetime) -> int:
        """Pending terminals whose pairing code is still valid."""
        ...

    async def get_pending_pairing_codes(self) -> set[str]:
        """The codes every pending terminal holds, expired ones included,
        since the unique index covers them all."""
        ...

    async def delete_stale_pending(self, expired_before: datetime) -> int:
        """Deletes pending terminals whose code expired before the given
        time and returns how many it removed."""
        ...

    async def save(self, terminal: Terminal) -> Terminal: ...

    async def delete(self, terminal: Terminal) -> None: ...
