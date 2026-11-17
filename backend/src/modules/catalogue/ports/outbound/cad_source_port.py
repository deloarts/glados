"""
What Catalogue needs to know about the connected CAD source when it writes or
shows an item: whether a CAD source owns a part number space and CAD rows,
and whether those rows refuse web changes to the fields the CAD source owns.
Catalogue owns this port and CAD & external data implements it, so item code
never reads the PDM settings itself and a second CAD source is a second
implementation.
"""

from dataclasses import dataclass
from typing import Protocol
from typing import runtime_checkable

from src.modules.platform.domain.entities.user import User


@dataclass(frozen=True)
class CadPolicy:
    """`connected` is true while a CAD source is switched on and configured:
    its part number pattern is reserved for ingest and web creation may be
    switched off. `rows_read_only` is true while connected and CAD rows
    refuse web changes to the fields the CAD source owns
    (docs/FIELD_OWNERSHIP.md)."""

    connected: bool
    rows_read_only: bool

    def enforces_ownership_for(self, actor: User) -> bool:
        """Whether a write by `actor` is held to the CAD ownership. Ingest
        runs as the system user, which is the CAD source itself."""
        return self.rows_read_only and not actor.is_systemuser


@runtime_checkable
class ICadSource(Protocol):
    async def policy(self) -> CadPolicy:
        """The policy of the CAD source as it is configured now."""
        ...
