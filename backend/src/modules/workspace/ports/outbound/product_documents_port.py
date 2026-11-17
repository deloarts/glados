"""
What Workspace needs to know about the documents of a product, which
Quality & documents owns: how many released calculations and checklists a
renumbering would leave showing the old number and how many exports they
have, and which devices its sequences reference. Workspace owns this port
and Quality & documents implements it, so product code never reads the
documents itself.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ProductDocumentCounts:
    """At least one released calculation or checklist counts as one each
    (`released`), and `exports` counts the exported reports of every
    calculation and checklist lineage of the product."""

    released: int
    exports: int


@dataclass(frozen=True)
class SequencedDevices:
    """The devices a valid released sequence references, and those only the
    latest unreleased draft references."""

    released: frozenset[int]
    drafts: frozenset[int]


class IProductDocuments(Protocol):
    async def renumber_counts(self, product_id: int) -> ProductDocumentCounts: ...

    async def sequenced_devices(self, product_id: int) -> SequencedDevices: ...
