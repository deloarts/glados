"""
Repository interface for infoscreens.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.operations.domain.entities.infoscreen import Infoscreen
from src.modules.operations.domain.value_objects.display_schedule import DisplayScheduleDefault


@runtime_checkable
class IInfoscreenRepository(Protocol):
    async def get_by_id(self, id: int) -> Infoscreen | None:
        """Regardless of `archived`, so a terminal's screen always resolves."""
        ...

    async def get_all(self, *, include_archived: bool) -> list[Infoscreen]:
        """Every screen, ordered by name."""
        ...

    async def get_live_by_name(self, name: str) -> Infoscreen | None:
        """The non-archived screen with this name, compared case-insensitively."""
        ...

    async def save(self, infoscreen: Infoscreen) -> Infoscreen: ...

    async def get_display_default(self) -> DisplayScheduleDefault:
        """The default display schedule; always on until one is saved."""
        ...

    async def save_display_default(
        self, default: DisplayScheduleDefault
    ) -> DisplayScheduleDefault: ...
