"""
What document control needs from the repository of any controlled
document, such as calculations or checklists. Each kind's own repository
port provides it alongside its other queries.
"""

from typing import Protocol
from typing import TypeVar
from uuid import UUID

from src.modules.quality.domain.entities.controlled_document import ControlledDocument

D = TypeVar("D", bound=ControlledDocument)


class IControlledDocumentRepository(Protocol[D]):
    async def get_by_id(self, id: int) -> D | None: ...

    async def get_for_update(self, id: int) -> D | None:
        """The document read under a row lock (FOR NO KEY UPDATE) on every
        revision of its lineage, held until the caller's transaction ends.
        Every document control step and content save reads through it, so
        two of them on one document, or on two revisions whose release,
        deletion or invalidation touches the other, run one after the
        other and each sees what the other committed."""
        ...

    async def get_by_public_id(self, public_id: UUID) -> D | None: ...

    async def get_lineage(self, lineage: UUID) -> list[D]:
        """Every revision of one document, newest revision first."""
        ...

    async def next_document_number(self, template: str) -> str:
        """The next free document number for a numbering template."""
        ...

    async def save(self, item: D) -> D: ...
    async def delete(self, item: D) -> None: ...
