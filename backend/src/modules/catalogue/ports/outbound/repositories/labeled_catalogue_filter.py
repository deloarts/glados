"""
The list filter shared by the labeled catalogue entities (article groups,
source item types, fabrication methods and inspection methods). Each
repository port keeps its own subclass, so a caller still names the filter of
the entity it lists and a filter for one entity never compares equal to a
filter for another.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class LabeledCatalogueFilterDto:
    skip: int | None = None
    limit: int | None = None
    search: str | None = None
    id: int | None = None
    name: str | None = None
    creator_id: int | None = None
    changed_by_id: int | None = None
    include_archived: bool = False
    created_from: datetime | None = None
    created_to: datetime | None = None
    changed_from: datetime | None = None
    changed_to: datetime | None = None
    order_by: str | None = None
    order_dir: str | None = None
    # The languages a name sort prefers, in order; the first language with
    # a text wins after them.
    languages: tuple[str, ...] = ()
