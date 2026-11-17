"""
Abstract interface for the global search feature (`GET /search`). Mirrors
public_id_resolver.py's shape: a small Protocol plus the dataclasses it
returns, no entity/dto mapping here.

`LiveResource` (src.modules.platform.ports.outbound.live_signal) is the canonical vocabulary
for these resource strings, but this is a port module and ports may not
import from src.application (import-linter's layered-architecture
contract: adapters -> application -> ports -> domain), so `SearchResource`
holds the same values as literals and SEARCH_RESOURCES lists them.
tests/unit/test_global_search_use_case.py asserts the two stay in sync.

SEARCH_RESOURCES are the groups every signed-in user gets. Contacts are
personal data, so their group is searched on its own (`search_contacts`)
and only for a reader of contacts, after the others.
"""

from dataclasses import dataclass
from typing import Literal
from typing import Protocol
from typing import get_args
from typing import runtime_checkable
from uuid import UUID

SearchResource = Literal[
    "products",
    "projects",
    "bought-items",
    "made-items",
    "source-items",
    "orders",
    "production-lots",
    "production-orders",
    "calculations",
    "checklists",
    "meetings",
    "contacts",
]
# Every resource but contacts, in the order the groups are returned.
SEARCH_RESOURCES: tuple[str, ...] = tuple(r for r in get_args(SearchResource) if r != "contacts")
CONTACT_SEARCH_RESOURCE = "contacts"

# How a hit matched the term: by tier, or for "related" through the record
# named by the hit's via kind.
SearchMatchKind = Literal["exact", "prefix", "contains", "related", "fuzzy"]
SearchViaKind = Literal["item", "project", "product", "customer", "supplier", "lot"]


@dataclass(frozen=True)
class SearchHitDetails:
    status: str | None = None
    article_name: str | None = None
    part_number: str | None = None
    order_code_1: str | None = None
    revision: str | None = None
    item_count: int | None = None
    supplier_name: str | None = None
    made_item_id: int | None = None
    made_item_part_number: str | None = None
    made_item_revision: str | None = None
    made_item_article_name: str | None = None
    source_label: str | None = None
    steps: list[str] | None = None
    execution_kind: str | None = None
    execution_label: str | None = None


@dataclass(frozen=True)
class SearchHit:
    resource: str
    id: int
    public_id: UUID
    label: str
    subtitle: str | None
    details: SearchHitDetails | None = None
    match_kind: str = "contains"
    via_kind: str | None = None


@dataclass(frozen=True)
class SearchGroup:
    resource: str
    total: int
    items: list[SearchHit]


@runtime_checkable
class IGlobalSearchRepository(Protocol):
    async def search(self, term: str, limit: int) -> list[SearchGroup]: ...

    async def search_contacts(self, term: str, limit: int) -> SearchGroup:
        """Live contacts by name, then e-mail address and organisation."""
        ...
