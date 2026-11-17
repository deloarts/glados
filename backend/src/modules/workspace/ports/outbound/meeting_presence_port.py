"""
Spreads who edits which meeting card to every open meeting page. The
signal is fleeting: nothing is stored, and a viewer forgets an editor 45
seconds after the last heartbeat.
"""

from typing import Protocol


class IMeetingPresence(Protocol):
    async def announce(self, card_id: int, user_id: int, *, editing: bool) -> None:
        """Best effort: a lost signal heals with the next heartbeat."""
        ...
