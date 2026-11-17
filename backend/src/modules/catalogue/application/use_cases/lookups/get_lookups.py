"""
Backs GET /pat/lookups: the add-in's offline cache bootstrap, one call
instead of six capped list requests, with a weak ETag so a 304
short-circuits before any of the tables is paged into a full payload.

Permission: mirrors the six individual PAT list endpoints this replaces
(suppliers, article_groups, fabrication_methods, inspection_methods,
source_item_types, source_items): none of them gates reads by permission
today (a valid PAT is the only requirement), so there is nothing further
to assert here. If any of the six ever gains a read permission, add the
matching assert_has_permission call here to keep this endpoint's gate a
superset of theirs, mirroring their own read permission.

Customers have no `pat` list endpoint. The bundle carries only their id,
name and archived flag, which the add-in's customer-item picker needs.
"""

import hashlib
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Sequence
from typing import TypeVar

from src.modules.catalogue.application.dto.lookups_dto import CustomerLookupResult
from src.modules.catalogue.application.dto.lookups_dto import LookupsResult
from src.modules.catalogue.application.mappers.article_group_mapper import ArticleGroupMapper
from src.modules.catalogue.application.mappers.fabrication_method_mapper import (
    FabricationMethodMapper,
)
from src.modules.catalogue.application.mappers.inspection_method_mapper import (
    InspectionMethodMapper,
)
from src.modules.catalogue.application.mappers.source_item_mapper import SourceItemMapper
from src.modules.catalogue.application.mappers.source_item_type_mapper import SourceItemTypeMapper
from src.modules.catalogue.application.mappers.supplier_mapper import SupplierMapper
from src.modules.catalogue.ports.outbound.catalogue_queries import ArticleGroupFilterDto
from src.modules.catalogue.ports.outbound.catalogue_queries import SupplierFilterDto
from src.modules.catalogue.ports.outbound.repositories.article_group_repository import (
    IArticleGroupRepository,
)
from src.modules.catalogue.ports.outbound.repositories.customer_repository import CustomerFilterDto
from src.modules.catalogue.ports.outbound.repositories.customer_repository import (
    ICustomerRepository,
)
from src.modules.catalogue.ports.outbound.repositories.fabrication_method_repository import (
    FabricationMethodFilterDto,
)
from src.modules.catalogue.ports.outbound.repositories.fabrication_method_repository import (
    IFabricationMethodRepository,
)
from src.modules.catalogue.ports.outbound.repositories.inspection_method_repository import (
    IInspectionMethodRepository,
)
from src.modules.catalogue.ports.outbound.repositories.inspection_method_repository import (
    InspectionMethodFilterDto,
)
from src.modules.catalogue.ports.outbound.repositories.source_item_repository import (
    ISourceItemRepository,
)
from src.modules.catalogue.ports.outbound.repositories.source_item_repository import (
    SourceItemFilterDto,
)
from src.modules.catalogue.ports.outbound.repositories.source_item_type_repository import (
    ISourceItemTypeRepository,
)
from src.modules.catalogue.ports.outbound.repositories.source_item_type_repository import (
    SourceItemTypeFilterDto,
)
from src.modules.catalogue.ports.outbound.repositories.supplier_repository import (
    ISupplierRepository,
)
from src.modules.platform.application.services.paging import fetch_all
from src.shared_kernel.domain.services.clock import now_utc
from src.shared_kernel.domain.services.list_order import ListEntry

# Page size for the internal exhaustive fetch loop below: the largest a
# single get_multi call is ever allowed to return (pagination.clamp_page),
# not a limit on the endpoint's own "all rows" contract.
_BATCH_SIZE = 500


class GetLookups:
    def __init__(
        self,
        supplier_repo: ISupplierRepository,
        article_group_repo: IArticleGroupRepository,
        fabrication_method_repo: IFabricationMethodRepository,
        inspection_method_repo: IInspectionMethodRepository,
        source_item_type_repo: ISourceItemTypeRepository,
        source_item_repo: ISourceItemRepository,
        customer_repo: ICustomerRepository,
    ) -> None:
        self._suppliers = supplier_repo
        self._article_groups = article_group_repo
        self._fabrication_methods = fabrication_method_repo
        self._inspection_methods = inspection_method_repo
        self._source_item_types = source_item_type_repo
        self._source_items = source_item_repo
        self._customers = customer_repo

    async def compute_etag(self, label_languages: Sequence[str] = ()) -> str:
        """Weak ETag from one cheap (count, max(changed)) aggregate query
        per table. Never builds the payload, so a 304 stays cheap
        regardless of how large the tables are. `label_languages` are the
        languages the payload's catalogue labels are resolved in, so a
        change of the add-in language invalidates a cached payload.

        A move or a place rewrites only `sort_order` and leaves `changed`
        alone, so the hand-ordered families also fold every row's place
        into the tag; otherwise a reordered list would keep answering 304.
        Those are the small lookup families, read as (id, sort_order)
        pairs only, so this stays cheap too."""
        aggregates = [
            ("suppliers", *(await self._suppliers.get_aggregate())),
            ("article_groups", *(await self._article_groups.get_aggregate())),
            ("fabrication_methods", *(await self._fabrication_methods.get_aggregate())),
            ("inspection_methods", *(await self._inspection_methods.get_aggregate())),
            ("source_item_types", *(await self._source_item_types.get_aggregate())),
            ("source_items", *(await self._source_items.get_aggregate())),
            ("customers", *(await self._customers.get_aggregate())),
        ]
        fingerprint = "|".join(
            f"{table}:{count}:{changed.isoformat() if changed else ''}"
            for table, count, changed in aggregates
        )
        fingerprint += "|order:" + await self._order_fingerprint()
        fingerprint += "|labels:" + ",".join(label_languages)
        return hashlib.sha256(fingerprint.encode()).hexdigest()[:32]

    async def _order_fingerprint(self) -> str:
        """Every row's place in the hand-ordered families, by id."""
        orders = [
            ("article_groups", await self._article_groups.get_list_order()),
            ("fabrication_methods", await self._fabrication_methods.get_list_order()),
            ("inspection_methods", await self._inspection_methods.get_list_order()),
            ("source_item_types", await self._source_item_types.get_list_order()),
        ]
        return "|".join(
            f"{table}:" + ",".join(f"{e.id}={e.sort_order}" for e in sorted(entries, key=_by_id))
            for table, entries in orders
        )

    async def execute(self) -> LookupsResult:
        # Sequential on purpose: all repositories share one session,
        # which must never run two queries concurrently.
        suppliers = await _fetch_all(self._suppliers.get_multi, SupplierFilterDto)
        article_groups = await _fetch_all(self._article_groups.get_multi, ArticleGroupFilterDto)
        fabrication_methods = await _fetch_all(
            self._fabrication_methods.get_multi, FabricationMethodFilterDto
        )
        inspection_methods = await _fetch_all(
            self._inspection_methods.get_multi, InspectionMethodFilterDto
        )
        source_item_types = await _fetch_all(
            self._source_item_types.get_multi, SourceItemTypeFilterDto
        )
        source_items = await _fetch_all(self._source_items.get_multi, SourceItemFilterDto)
        customers = await _fetch_all(self._customers.get_multi, CustomerFilterDto)
        return LookupsResult(
            server_time=now_utc(),
            suppliers=[SupplierMapper.to_result(e) for e in suppliers],
            article_groups=[ArticleGroupMapper.to_result(e) for e in article_groups],
            fabrication_methods=[FabricationMethodMapper.to_result(e) for e in fabrication_methods],
            inspection_methods=[InspectionMethodMapper.to_result(e) for e in inspection_methods],
            source_item_types=[SourceItemTypeMapper.to_result(e) for e in source_item_types],
            source_items=[SourceItemMapper.to_result(e) for e in source_items],
            customers=[
                CustomerLookupResult(id=e.id, name=e.name, archived=e.archived) for e in customers
            ],
        )


def _by_id(entry: ListEntry) -> int:
    return entry.id


T = TypeVar("T")
F = TypeVar("F")


async def _fetch_all(
    get_multi: Callable[[F], Awaitable[tuple[int, list[T]]]], filter_dto_cls: Callable[..., F]
) -> list[T]:
    """Exhausts get_multi's own MAX_PAGE_SIZE clamp (pagination.clamp_page)
    in batches, ordered by id, so the caller always gets every row
    (archived included) regardless of table size. `get_multi` is one of
    the repositories' own method, always shaped
    `(filters) -> tuple[int, list[entity]]`."""
    return await fetch_all(
        lambda skip, limit: get_multi(
            filter_dto_cls(include_archived=True, skip=skip, limit=limit, order_by="id")
        ),
        _BATCH_SIZE,
    )
