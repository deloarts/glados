"""
Repository interface for PrintTemplate. Settings-style: InitDatabase creates
one unconfigured slot per classifier through save(), and from then on rows are
only edited, so there is no delete() here.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.quality.domain.entities.print_template import PrintTemplate


@runtime_checkable
class IPrintTemplateRepository(Protocol):
    async def get_by_classifier(self, classifier: str) -> PrintTemplate | None: ...
    async def get_all(self) -> list[PrintTemplate]: ...
    async def get_armed_by_trigger(self, trigger: str) -> list[PrintTemplate]:
        """Templates bound to `trigger` with auto_print, enabled and a
        printer set: the auto-print handler's candidate set."""
        ...

    async def save(self, item: PrintTemplate) -> PrintTemplate:
        """Inserts a template with id 0, otherwise updates the row with its id."""
        ...
