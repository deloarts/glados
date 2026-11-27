"""
Repository interface for the Printer catalogue aggregate.
"""

from dataclasses import dataclass
from typing import Protocol
from typing import runtime_checkable

from src.modules.quality.domain.entities.printer import Printer


@dataclass
class PrinterFilterDto:
    skip: int | None = None
    limit: int | None = None
    search: str | None = None
    id: int | None = None
    name: str | None = None
    kind: str | None = None
    enabled: bool | None = None
    creator_id: int | None = None
    changed_by_id: int | None = None
    include_archived: bool = False
    order_by: str | None = None
    order_dir: str | None = None


@runtime_checkable
class IPrinterRepository(Protocol):
    async def get_by_id(self, id: int) -> Printer | None:
        """Regardless of `archived`, references must resolve."""
        ...

    async def get_multi(self, filters: PrinterFilterDto) -> tuple[int, list[Printer]]: ...
    async def save(self, item: Printer) -> Printer: ...
    async def delete(self, item: Printer) -> None: ...

    async def clear_default_except(self, id: int) -> None:
        """Clears `is_default` on every printer but the given one, so a
        printer that becomes the default replaces the previous one in the
        same transaction."""
        ...
