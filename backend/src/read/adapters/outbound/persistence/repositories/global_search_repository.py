"""Concrete implementation of IGlobalSearchRepository using SQLAlchemy with a 4-tier ranking
system: exact matches, prefix matches, contains matches, and related matches (items found
through linked entity FKs), plus a fuzzy fallback tier using pg_trgm similarity. Portable SQL
(ILIKE + OR + CASE + LIMIT/count()) runs identically on SQLite and Postgres, so the integration
suite's SQLite run and production Postgres behave the same. One private helper per resource;
`search()` returns them in SEARCH_RESOURCES order.

Every hit carries `match_kind` (exact | prefix | contains | related | fuzzy) and, for related
hits, `via_kind`. The fuzzy tier uses pg_trgm `similarity()` on Postgres; the SQLite integration
suite gets a pure-Python approximation registered in tests/integration/conftest.py.

`_identifier_rank` (the plain 3-tier CASE) stays in use for made-items, the one resource with
no related tier (no supplier/customer FK). Every other resource uses `_rank_with_related`, the
4-tier extension.

"Match sets" are built once as module-level helper functions taking the already-escaped
`%pattern%` string, so every resource's related-tier check and via_kind CASE reuse the same
subqueries.
"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import ColumnElement
from sqlalchemy import Row
from sqlalchemy import Select
from sqlalchemy import case
from sqlalchemy import exists
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.orm import aliased
from sqlalchemy.orm import selectinload

from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model import (
    BoughtItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.contact_model import ContactOrmModel
from src.modules.catalogue.adapters.outbound.persistence.models.customer_model import (
    CustomerOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.made_item_model import (
    MadeItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.source_item_model import (
    SourceItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.source_item_type_model import (
    SourceItemTypeOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.supplier_model import (
    SupplierOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model import (
    LotPositionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_step_model import (
    LotStepOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_model import OrderOrmModel
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model import (
    ProductionOrderOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_demand_item_model import (
    SourceItemDemandItemOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.like_escape import escape_like
from src.modules.platform.adapters.outbound.persistence.localized_text_sql import localized_texts
from src.modules.platform.adapters.outbound.persistence.statements import count_rows
from src.modules.platform.infrastructure.label_languages import resolve_label
from src.modules.platform.ports.outbound.live_signal import LiveResource
from src.modules.quality.adapters.outbound.persistence.models.calculation_model import (
    CalculationOrmModel,
)
from src.modules.quality.adapters.outbound.persistence.models.checklist_model import (
    ChecklistOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.meeting_model import MeetingOrmModel
from src.modules.workspace.adapters.outbound.persistence.models.product_model import ProductOrmModel
from src.modules.workspace.adapters.outbound.persistence.models.project_model import ProjectOrmModel
from src.read.ports.outbound.repositories.global_search_repository import CONTACT_SEARCH_RESOURCE
from src.read.ports.outbound.repositories.global_search_repository import SEARCH_RESOURCES
from src.read.ports.outbound.repositories.global_search_repository import IGlobalSearchRepository
from src.read.ports.outbound.repositories.global_search_repository import SearchGroup
from src.read.ports.outbound.repositories.global_search_repository import SearchHit
from src.read.ports.outbound.repositories.global_search_repository import SearchHitDetails

_TextColumn = ColumnElement[Any] | InstrumentedAttribute[Any]

# SQL rank value -> match_kind string. Only 0-3 ever come back from a
# rank CASE; "fuzzy" is never a SQL rank, it is assigned in Python for rows
# returned by the separate fuzzy fallback query.
_RANK_TO_KIND: dict[int, str] = {0: "exact", 1: "prefix", 2: "contains", 3: "related"}

# pg_trgm's default similarity threshold.
_FUZZY_THRESHOLD = 0.3


def _contains(cols: Sequence[_TextColumn], pattern: str) -> ColumnElement[bool]:
    return or_(*(col.ilike(pattern, escape="\\") for col in cols))


def _identifier_rank(idents: Sequence[_TextColumn], t: str, prefix: str) -> ColumnElement[int]:
    return case(
        (or_(*(func.lower(c) == t for c in idents)), 0),
        (or_(*(func.lower(c).like(prefix, escape="\\") for c in idents)), 1),
        else_=2,
    )


def _rank_with_related(
    idents: Sequence[_TextColumn],
    secondaries: Sequence[_TextColumn],
    t: str,
    prefix: str,
    contains: str,
    related: ColumnElement[bool],
) -> ColumnElement[int]:
    """The 4-tier extension of `_identifier_rank`: 0 exact, 1 prefix,
    2 contains (own columns), 3 related. The `related` branch is
    only reachable when the caller's WHERE clause is
    `_contains(idents + secondaries, contains) OR related`; a row that
    reaches this CASE without matching its own columns got there only
    through `related`."""
    return case(
        (or_(*(func.lower(c) == t for c in idents)), 0),
        (or_(*(func.lower(c).like(prefix, escape="\\") for c in idents)), 1),
        (_contains(list(idents) + list(secondaries), contains), 2),
        else_=3,
    )


def _patterns(term: str) -> tuple[str, str, str]:
    """The lowered term and its escaped contains and prefix LIKE patterns."""
    t = term.lower()
    return t, f"%{escape_like(t)}%", f"{escape_like(t)}%"


def _similarity_filter(idents: Sequence[_TextColumn], term: str) -> ColumnElement[bool]:
    """Any tier-A column scoring >= the pg_trgm default threshold."""
    return or_(*(func.similarity(c, term) >= _FUZZY_THRESHOLD for c in idents))


def _similarity_order(ident_primary: _TextColumn, term: str) -> ColumnElement[Any]:
    return func.similarity(ident_primary, term).desc()


# ── B2 match sets ────────────────────────────────────────────────────
#
# Each returns a SELECT of ids whose identifier columns ILIKE the pattern,
# restricted to non-deleted rows. Used both inside a related-tier
# `.in_(...)` check and inside a via_kind CASE, so every resource's
# related-ness test and its via_kind attribution stay in lockstep.


def _made_match_set(pattern: str) -> Any:
    return select(MadeItemOrmModel.id).where(
        MadeItemOrmModel.archived.is_(False),
        _contains([MadeItemOrmModel.article_name, MadeItemOrmModel.part_number], pattern),
    )


def _bought_match_set(pattern: str) -> Any:
    return select(BoughtItemOrmModel.id).where(
        BoughtItemOrmModel.archived.is_(False),
        _contains(
            [
                BoughtItemOrmModel.article_name,
                BoughtItemOrmModel.order_code_1,
                BoughtItemOrmModel.order_code_2,
                BoughtItemOrmModel.part_number,
            ],
            pattern,
        ),
    )


def _source_match_set(pattern: str) -> Any:
    return select(SourceItemOrmModel.id).where(
        SourceItemOrmModel.archived.is_(False),
        _contains(
            [
                SourceItemOrmModel.material,
                SourceItemOrmModel.order_code_1,
                SourceItemOrmModel.order_code_2,
            ],
            pattern,
        ),
    )


def _project_match_set(pattern: str) -> Any:
    return select(ProjectOrmModel.id).where(
        ProjectOrmModel.deleted.is_(False),
        ProjectOrmModel.project_number.ilike(pattern, escape="\\"),
    )


def _product_match_set(pattern: str) -> Any:
    return select(ProductOrmModel.id).where(
        ProductOrmModel.archived.is_(False),
        ProductOrmModel.product_number.ilike(pattern, escape="\\"),
    )


def _customer_match_set(pattern: str) -> Any:
    return select(CustomerOrmModel.id).where(
        CustomerOrmModel.archived.is_(False),
        _contains([CustomerOrmModel.name, CustomerOrmModel.legal_name], pattern),
    )


def _supplier_match_set(pattern: str) -> Any:
    return select(SupplierOrmModel.id).where(
        SupplierOrmModel.archived.is_(False),
        _contains([SupplierOrmModel.name, SupplierOrmModel.legal_name], pattern),
    )


# ── B2 per-resource related-ness + via_kind ─────────────────────────


def _project_related(pattern: str) -> ColumnElement[bool]:
    return or_(
        ProjectOrmModel.customer_id.in_(_customer_match_set(pattern)),
        ProjectOrmModel.product_id.in_(_product_match_set(pattern)),
    )


def _project_via_kind(pattern: str) -> ColumnElement[Any]:
    # B1 priority order (item, project, product, customer, supplier, lot);
    # projects only ever offer the product/customer routes.
    return case(
        (ProjectOrmModel.product_id.in_(_product_match_set(pattern)), "product"),
        (ProjectOrmModel.customer_id.in_(_customer_match_set(pattern)), "customer"),
        else_=None,
    )


def _product_related(pattern: str) -> ColumnElement[bool]:
    return ProductOrmModel.customer_id.in_(_customer_match_set(pattern))


def _bought_item_related(pattern: str) -> ColumnElement[bool]:
    return BoughtItemOrmModel.manufacturer_id.in_(_supplier_match_set(pattern))


def _source_item_related(pattern: str) -> ColumnElement[bool]:
    return SourceItemOrmModel.manufacturer_id.in_(_supplier_match_set(pattern))


def _order_item_route(pattern: str) -> ColumnElement[bool]:
    matched_lots = select(ProductionLotOrmModel.id).where(
        ProductionLotOrmModel.made_item_id.in_(_made_match_set(pattern))
    )
    matched_positions = select(LotPositionOrmModel.id).where(
        LotPositionOrmModel.lot_id.in_(matched_lots)
    )
    return exists(
        select(OrderItemOrmModel.id).where(
            OrderItemOrmModel.order_id == OrderOrmModel.id,
            or_(
                OrderItemOrmModel.bought_item_id.in_(_bought_match_set(pattern)),
                OrderItemOrmModel.source_item_id.in_(_source_match_set(pattern)),
                OrderItemOrmModel.lot_position_id.in_(matched_positions),
            ),
        )
    )


def _order_project_route(pattern: str) -> ColumnElement[bool]:
    return exists(
        select(OrderItemOrmModel.id).where(
            OrderItemOrmModel.order_id == OrderOrmModel.id,
            OrderItemOrmModel.project_id.in_(_project_match_set(pattern)),
        )
    )


def _order_supplier_route(pattern: str) -> ColumnElement[bool]:
    return OrderOrmModel.supplier_id.in_(_supplier_match_set(pattern))


def _order_related(pattern: str) -> ColumnElement[bool]:
    return or_(
        _order_item_route(pattern),
        _order_project_route(pattern),
        _order_supplier_route(pattern),
    )


def _order_via_kind(pattern: str) -> ColumnElement[Any]:
    return case(
        (_order_item_route(pattern), "item"),
        (_order_project_route(pattern), "project"),
        (_order_supplier_route(pattern), "supplier"),
        else_=None,
    )


def _lot_demand_linked(pattern: str) -> ColumnElement[bool]:
    return exists(
        select(SourceItemDemandItemOrmModel.id).where(
            SourceItemDemandItemOrmModel.lot_id == ProductionLotOrmModel.id,
            or_(
                SourceItemDemandItemOrmModel.source_item_id.in_(_source_match_set(pattern)),
                SourceItemDemandItemOrmModel.bought_item_id.in_(_bought_match_set(pattern)),
            ),
        )
    )


def _lot_item_route(pattern: str) -> ColumnElement[bool]:
    return or_(
        ProductionLotOrmModel.made_item_id.in_(_made_match_set(pattern)),
        ProductionLotOrmModel.source_item_id.in_(_source_match_set(pattern)),
        ProductionLotOrmModel.source_bought_item_id.in_(_bought_match_set(pattern)),
        ProductionLotOrmModel.source_made_item_id.in_(_made_match_set(pattern)),
        _lot_demand_linked(pattern),
    )


def _lot_project_route(pattern: str) -> ColumnElement[bool]:
    return ProductionLotOrmModel.project_id.in_(_project_match_set(pattern))


def _lot_product_route(pattern: str) -> ColumnElement[bool]:
    return ProductionLotOrmModel.project_id.in_(
        select(ProjectOrmModel.id).where(
            ProjectOrmModel.product_id.in_(_product_match_set(pattern))
        )
    )


def _lot_customer_route(pattern: str) -> ColumnElement[bool]:
    return ProductionLotOrmModel.project_id.in_(
        select(ProjectOrmModel.id).where(
            ProjectOrmModel.customer_id.in_(_customer_match_set(pattern))
        )
    )


def _lot_related(pattern: str) -> ColumnElement[bool]:
    return or_(
        _lot_item_route(pattern),
        _lot_project_route(pattern),
        _lot_product_route(pattern),
        _lot_customer_route(pattern),
    )


def _lot_via_kind(pattern: str) -> ColumnElement[Any]:
    return case(
        (_lot_item_route(pattern), "item"),
        (_lot_project_route(pattern), "project"),
        (_lot_product_route(pattern), "product"),
        (_lot_customer_route(pattern), "customer"),
        else_=None,
    )


def _lot_own_contains(pattern: str) -> ColumnElement[bool]:
    """A production order's lot matches the lot's OWN identifier
    (lot_number). This is the `production-orders` row's `via_kind="lot"`
    case."""
    return ProductionLotOrmModel.lot_number.ilike(pattern, escape="\\")


def _production_order_related(pattern: str) -> ColumnElement[bool]:
    return or_(_lot_own_contains(pattern), _lot_related(pattern))


def _production_order_via_kind(pattern: str) -> ColumnElement[Any]:
    return case(
        (_lot_own_contains(pattern), "lot"),
        (_lot_item_route(pattern), "item"),
        (_lot_project_route(pattern), "project"),
        (_lot_product_route(pattern), "product"),
        (_lot_customer_route(pattern), "customer"),
        else_=None,
    )


# ── A1 detail helpers (unchanged) ────────────────────────────────────


def _lot_source_label(lot: ProductionLotOrmModel) -> str | None:
    """The `source_label` rule: exactly one of the three source
    relationships is set on a lot (or none, per the model's docstring)."""
    if lot.source_item is not None:
        dimension = lot.source_item.dimension or ""
        material = lot.source_item.material or ""
        return f"{dimension} {material}".strip() or None
    if lot.source_bought_item is not None:
        return lot.source_bought_item.article_name
    if lot.source_made_item is not None:
        return lot.source_made_item.part_number or lot.source_made_item.article_name
    return None


def _execution_kind(order: ProductionOrderOrmModel) -> str:
    if order.machine_id is not None:
        return "machine"
    if order.machine_pool_id is not None:
        return "pool"
    return "manual"


def _execution_label(order: ProductionOrderOrmModel) -> str | None:
    if order.machine_id is not None:
        return order.machine.internal_name if order.machine else None
    if order.machine_pool_id is not None:
        return order.machine_pool.name if order.machine_pool else None
    return None


# ── Row -> SearchHit mapping, one per resource, reused by the strict
# (tiers 0-3) and fuzzy queries alike. ───────────────────────────────


def _map_product(r: ProductOrmModel, match_kind: str, via_kind: str | None) -> SearchHit:
    return SearchHit(
        resource=LiveResource.PRODUCTS,
        id=r.id,
        public_id=r.public_id,
        label=r.product_number,
        subtitle=r.description,
        match_kind=match_kind,
        via_kind=via_kind,
    )


def _map_project(r: ProjectOrmModel, match_kind: str, via_kind: str | None) -> SearchHit:
    return SearchHit(
        resource=LiveResource.PROJECTS,
        id=r.id,
        public_id=r.public_id,
        label=r.project_number,
        subtitle=r.description,
        match_kind=match_kind,
        via_kind=via_kind,
    )


def _map_bought_item(r: BoughtItemOrmModel, match_kind: str, via_kind: str | None) -> SearchHit:
    return SearchHit(
        resource=LiveResource.BOUGHT_ITEMS,
        id=r.id,
        public_id=r.public_id,
        label=r.article_name,
        subtitle=r.order_code_1,
        match_kind=match_kind,
        via_kind=via_kind,
        details=SearchHitDetails(
            article_name=r.article_name,
            part_number=r.part_number,
            order_code_1=r.order_code_1,
        ),
    )


def _map_made_item(r: MadeItemOrmModel, match_kind: str, via_kind: str | None) -> SearchHit:
    return SearchHit(
        resource=LiveResource.MADE_ITEMS,
        id=r.id,
        public_id=r.public_id,
        label=r.article_name,
        subtitle=r.part_number,
        match_kind=match_kind,
        via_kind=via_kind,
        details=SearchHitDetails(
            article_name=r.article_name,
            part_number=r.part_number,
            revision=r.revision,
        ),
    )


def _map_source_item(r: SourceItemOrmModel, match_kind: str, via_kind: str | None) -> SearchHit:
    return SearchHit(
        resource=LiveResource.SOURCE_ITEMS,
        id=r.id,
        public_id=r.public_id,
        label=r.material,
        subtitle=r.dimension,
        match_kind=match_kind,
        via_kind=via_kind,
    )


def _map_order(
    r: OrderOrmModel, item_count: int, match_kind: str, via_kind: str | None
) -> SearchHit:
    return SearchHit(
        resource=LiveResource.ORDERS,
        id=r.id,
        public_id=r.public_id,
        label=r.order_number,
        subtitle=r.status,
        match_kind=match_kind,
        via_kind=via_kind,
        details=SearchHitDetails(
            status=r.status,
            item_count=item_count,
            supplier_name=r.supplier.name if r.supplier else None,
        ),
    )


def _map_production_lot(
    r: ProductionLotOrmModel, match_kind: str, via_kind: str | None
) -> SearchHit:
    return SearchHit(
        resource=LiveResource.PRODUCTION_LOTS,
        id=r.id,
        public_id=r.public_id,
        label=r.lot_number,
        subtitle=r.status,
        match_kind=match_kind,
        via_kind=via_kind,
        details=SearchHitDetails(
            status=r.status,
            made_item_id=r.made_item.id,
            made_item_part_number=r.made_item.part_number,
            made_item_revision=r.made_item.revision,
            made_item_article_name=r.made_item.article_name,
            source_label=_lot_source_label(r),
            steps=[
                resolve_label(step.fabrication_method.name)
                for position in r.positions
                for step in position.steps
                if step.fabrication_method is not None
            ],
        ),
    )


def _map_production_order(
    r: ProductionOrderOrmModel, match_kind: str, via_kind: str | None
) -> SearchHit:
    return SearchHit(
        resource=LiveResource.PRODUCTION_ORDERS,
        id=r.id,
        public_id=r.public_id,
        label=r.production_order_number,
        subtitle=r.status,
        match_kind=match_kind,
        via_kind=via_kind,
        details=SearchHitDetails(
            status=r.status,
            made_item_id=r.lot_position.lot.made_item.id,
            made_item_part_number=r.lot_position.lot.made_item.part_number,
            made_item_revision=r.lot_position.lot.made_item.revision,
            made_item_article_name=r.lot_position.lot.made_item.article_name,
            execution_kind=_execution_kind(r),
            execution_label=_execution_label(r),
        ),
    )


def _map_contact(r: ContactOrmModel, organisation: str | None, match_kind: str) -> SearchHit:
    """The contact's name, with its role and organisation below it."""
    subtitle = " · ".join(part for part in (r.role, organisation) if part)
    return SearchHit(
        resource=CONTACT_SEARCH_RESOURCE,
        id=r.id,
        public_id=r.public_id,
        label=r.name,
        subtitle=subtitle or None,
        match_kind=match_kind,
    )


def _map_meeting(r: MeetingOrmModel, match_kind: str) -> SearchHit:
    """The meeting's number, with its name below it and whether it is
    valid."""
    return SearchHit(
        resource=LiveResource.MEETINGS,
        id=r.id,
        public_id=r.public_id,
        label=r.meeting_number,
        subtitle=r.name,
        match_kind=match_kind,
        details=SearchHitDetails(status="invalid" if r.invalid_at is not None else "valid"),
    )


def _document_status(r: Any) -> str:
    if r.invalid_at is not None:
        return "invalid"
    return "released" if r.released_at is not None else "draft"


def _map_document(r: Any, resource: str, match_kind: str) -> SearchHit:
    return SearchHit(
        resource=resource,
        id=r.id,
        public_id=r.public_id,
        label=r.document_number,
        subtitle=r.title,
        match_kind=match_kind,
        details=SearchHitDetails(status=_document_status(r), revision=r.revision),
    )


class SqlAlchemyGlobalSearchRepository(IGlobalSearchRepository):
    """Implements IGlobalSearchRepository."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def search(self, term: str, limit: int) -> list[SearchGroup]:
        resolvers = {
            "products": self._products,
            "projects": self._projects,
            "bought-items": self._bought_items,
            "made-items": self._made_items,
            "source-items": self._source_items,
            "orders": self._orders,
            "production-lots": self._production_lots,
            "production-orders": self._production_orders,
            "calculations": self._calculations,
            "checklists": self._checklists,
            "meetings": self._meetings,
        }
        return [await resolvers[resource](term, limit) for resource in SEARCH_RESOURCES]

    async def _ranked_with_fuzzy(
        self,
        model: Any,
        base: Select[Any],
        rank: ColumnElement[int],
        term: str,
        limit: int,
        *,
        live: Sequence[ColumnElement[bool]],
        similar: Sequence[_TextColumn],
        columns: Sequence[ColumnElement[Any]] = (),
        fuzzy_columns: Sequence[ColumnElement[Any]] = (),
        options: Sequence[Any] = (),
    ) -> tuple[int, Sequence[Row[Any]], Sequence[Row[Any]]]:
        """Counts `base`, reads its first `limit` rows by `rank` then newest
        first, each as (row, rank, *columns), and tops a short page up with
        fuzzy hits, as (row, *fuzzy_columns): rows passing the `live`
        filters whose `similar` columns score above the threshold, best
        match on the first of them first, leaving out the rows the ranked
        page already returned."""
        total = await count_rows(self._db, base)
        ranked = (
            await self._db.execute(
                base.order_by(rank, model.id.desc())
                .limit(limit)
                .options(*options)
                .add_columns(rank.label("rank"), *columns)
            )
        ).all()
        if len(ranked) >= limit:
            return total, ranked, []
        fuzzy = (
            await self._db.execute(
                select(model)
                .where(
                    *live,
                    model.id.notin_([row[0].id for row in ranked]),
                    _similarity_filter(similar, term),
                )
                .order_by(_similarity_order(similar[0], term), model.id.desc())
                .limit(limit - len(ranked))
                .options(*options)
                .add_columns(*fuzzy_columns)
            )
        ).all()
        return total, ranked, fuzzy

    # ── Resources ─────────────────────────────────────────────────────

    async def _products(self, term: str, limit: int) -> SearchGroup:
        t, contains, prefix = _patterns(term)
        idents: list[_TextColumn] = [ProductOrmModel.product_number]
        secondaries: list[_TextColumn] = [ProductOrmModel.description]
        related = _product_related(contains)
        rank = _rank_with_related(idents, secondaries, t, prefix, contains, related)
        live = [ProductOrmModel.archived.is_(False)]
        base = select(ProductOrmModel).where(
            *live, or_(_contains(idents + secondaries, contains), related)
        )
        total, ranked, fuzzy = await self._ranked_with_fuzzy(
            ProductOrmModel, base, rank, term, limit, live=live, similar=idents
        )
        hits = [
            _map_product(r, _RANK_TO_KIND[rank_val], "customer" if rank_val == 3 else None)
            for r, rank_val in ranked
        ]
        hits += [_map_product(r, "fuzzy", None) for (r,) in fuzzy]
        return SearchGroup(resource=LiveResource.PRODUCTS, total=total, items=hits)

    async def _projects(self, term: str, limit: int) -> SearchGroup:
        t, contains, prefix = _patterns(term)
        idents: list[_TextColumn] = [ProjectOrmModel.project_number]
        secondaries: list[_TextColumn] = [ProjectOrmModel.description]
        related = _project_related(contains)
        via_kind = _project_via_kind(contains)
        rank = _rank_with_related(idents, secondaries, t, prefix, contains, related)
        live = [ProjectOrmModel.deleted.is_(False)]
        base = select(ProjectOrmModel).where(
            *live, or_(_contains(idents + secondaries, contains), related)
        )
        total, ranked, fuzzy = await self._ranked_with_fuzzy(
            ProjectOrmModel,
            base,
            rank,
            term,
            limit,
            live=live,
            similar=idents,
            columns=[via_kind.label("via_kind")],
        )
        hits = [
            _map_project(r, _RANK_TO_KIND[rank_val], via_kind_val if rank_val == 3 else None)
            for r, rank_val, via_kind_val in ranked
        ]
        hits += [_map_project(r, "fuzzy", None) for (r,) in fuzzy]
        return SearchGroup(resource=LiveResource.PROJECTS, total=total, items=hits)

    async def _bought_items(self, term: str, limit: int) -> SearchGroup:
        t, contains, prefix = _patterns(term)
        idents: list[_TextColumn] = [
            BoughtItemOrmModel.article_name,
            BoughtItemOrmModel.order_code_1,
            BoughtItemOrmModel.order_code_2,
            BoughtItemOrmModel.part_number,
        ]
        secondaries: list[_TextColumn] = [
            BoughtItemOrmModel.gtin,
            BoughtItemOrmModel.ean,
            BoughtItemOrmModel.note,
        ]
        related = _bought_item_related(contains)
        rank = _rank_with_related(idents, secondaries, t, prefix, contains, related)
        live = [BoughtItemOrmModel.archived.is_(False)]
        base = select(BoughtItemOrmModel).where(
            *live, or_(_contains(idents + secondaries, contains), related)
        )
        total, ranked, fuzzy = await self._ranked_with_fuzzy(
            BoughtItemOrmModel, base, rank, term, limit, live=live, similar=idents
        )
        hits = [
            _map_bought_item(r, _RANK_TO_KIND[rank_val], "supplier" if rank_val == 3 else None)
            for r, rank_val in ranked
        ]
        hits += [_map_bought_item(r, "fuzzy", None) for (r,) in fuzzy]
        return SearchGroup(resource=LiveResource.BOUGHT_ITEMS, total=total, items=hits)

    async def _made_items(self, term: str, limit: int) -> SearchGroup:
        # No related tier: made-items has no supplier/customer FK, so this is
        # the one resource that still uses the original 3-tier `_identifier_rank`.
        t, contains, prefix = _patterns(term)
        idents: list[_TextColumn] = [MadeItemOrmModel.article_name, MadeItemOrmModel.part_number]
        secondaries: list[_TextColumn] = [MadeItemOrmModel.material, MadeItemOrmModel.note]
        live = [MadeItemOrmModel.archived.is_(False)]
        base = select(MadeItemOrmModel).where(*live, _contains(idents + secondaries, contains))
        rank = _identifier_rank(idents, t, prefix)
        total, ranked, fuzzy = await self._ranked_with_fuzzy(
            MadeItemOrmModel, base, rank, term, limit, live=live, similar=idents
        )
        hits = [_map_made_item(r, _RANK_TO_KIND[rank_val], None) for r, rank_val in ranked]
        hits += [_map_made_item(r, "fuzzy", None) for (r,) in fuzzy]
        return SearchGroup(resource=LiveResource.MADE_ITEMS, total=total, items=hits)

    async def _source_items(self, term: str, limit: int) -> SearchGroup:
        t, contains, prefix = _patterns(term)
        idents: list[_TextColumn] = [
            SourceItemOrmModel.material,
            SourceItemOrmModel.order_code_1,
            SourceItemOrmModel.order_code_2,
        ]
        secondaries: list[_TextColumn] = [
            SourceItemOrmModel.dimension,
            SourceItemOrmModel.note,
            *localized_texts(SourceItemTypeOrmModel.name),
        ]
        related = _source_item_related(contains)
        rank = _rank_with_related(idents, secondaries, t, prefix, contains, related)
        live = [SourceItemOrmModel.archived.is_(False)]
        base = (
            select(SourceItemOrmModel)
            .join(SourceItemTypeOrmModel, SourceItemOrmModel.type_id == SourceItemTypeOrmModel.id)
            .where(*live, or_(_contains(idents + secondaries, contains), related))
        )
        total, ranked, fuzzy = await self._ranked_with_fuzzy(
            SourceItemOrmModel, base, rank, term, limit, live=live, similar=idents
        )
        hits = [
            _map_source_item(r, _RANK_TO_KIND[rank_val], "supplier" if rank_val == 3 else None)
            for r, rank_val in ranked
        ]
        hits += [_map_source_item(r, "fuzzy", None) for (r,) in fuzzy]
        return SearchGroup(resource=LiveResource.SOURCE_ITEMS, total=total, items=hits)

    async def _orders(self, term: str, limit: int) -> SearchGroup:
        t, contains, prefix = _patterns(term)
        idents: list[_TextColumn] = [OrderOrmModel.order_number]
        secondaries: list[_TextColumn] = [OrderOrmModel.note, OrderOrmModel.storage_place]
        related = _order_related(contains)
        via_kind = _order_via_kind(contains)
        rank = _rank_with_related(idents, secondaries, t, prefix, contains, related)
        item_count = (
            select(func.count(OrderItemOrmModel.id))
            .where(OrderItemOrmModel.order_id == OrderOrmModel.id)
            .scalar_subquery()
        )
        base = select(OrderOrmModel).where(
            or_(_contains(idents + secondaries, contains), related),
        )
        total, ranked, fuzzy = await self._ranked_with_fuzzy(
            OrderOrmModel,
            base,
            rank,
            term,
            limit,
            live=[],
            similar=idents,
            columns=[via_kind.label("via_kind"), item_count.label("item_count")],
            fuzzy_columns=[item_count.label("item_count")],
            options=[selectinload(OrderOrmModel.supplier)],
        )
        hits = [
            _map_order(r, count, _RANK_TO_KIND[rank_val], via_kind_val if rank_val == 3 else None)
            for r, rank_val, via_kind_val, count in ranked
        ]
        hits += [_map_order(r, count, "fuzzy", None) for r, count in fuzzy]
        return SearchGroup(resource=LiveResource.ORDERS, total=total, items=hits)

    async def _production_lots(self, term: str, limit: int) -> SearchGroup:
        t, contains, prefix = _patterns(term)
        idents: list[_TextColumn] = [ProductionLotOrmModel.lot_number]
        secondaries: list[_TextColumn] = [ProductionLotOrmModel.note]
        related = _lot_related(contains)
        via_kind = _lot_via_kind(contains)
        rank = _rank_with_related(idents, secondaries, t, prefix, contains, related)
        detail_options = (
            selectinload(ProductionLotOrmModel.made_item),
            selectinload(ProductionLotOrmModel.source_item),
            selectinload(ProductionLotOrmModel.source_bought_item),
            selectinload(ProductionLotOrmModel.source_made_item),
            selectinload(ProductionLotOrmModel.positions)
            .selectinload(LotPositionOrmModel.steps)
            .selectinload(LotStepOrmModel.fabrication_method),
        )
        base = select(ProductionLotOrmModel).where(
            or_(_contains(idents + secondaries, contains), related),
        )
        total, ranked, fuzzy = await self._ranked_with_fuzzy(
            ProductionLotOrmModel,
            base,
            rank,
            term,
            limit,
            live=[],
            similar=idents,
            columns=[via_kind.label("via_kind")],
            options=detail_options,
        )
        hits = [
            _map_production_lot(r, _RANK_TO_KIND[rank_val], via_kind_val if rank_val == 3 else None)
            for r, rank_val, via_kind_val in ranked
        ]
        hits += [_map_production_lot(r, "fuzzy", None) for (r,) in fuzzy]
        return SearchGroup(resource=LiveResource.PRODUCTION_LOTS, total=total, items=hits)

    async def _calculations(self, term: str, limit: int) -> SearchGroup:
        return await self._documents(CalculationOrmModel, LiveResource.CALCULATIONS, term, limit)

    async def _checklists(self, term: str, limit: int) -> SearchGroup:
        return await self._documents(ChecklistOrmModel, LiveResource.CHECKLISTS, term, limit)

    async def _documents(self, model: Any, resource: str, term: str, limit: int) -> SearchGroup:
        """The latest revision of each calculation or checklist, by its
        document number first and its title second. Personal documents are
        left out: search shows every user the same hits, and those are only
        their creator's to see."""
        t, contains, prefix = _patterns(term)
        idents: list[_TextColumn] = [model.document_number]
        secondaries: list[_TextColumn] = [model.title]
        rank = _identifier_rank(idents, t, prefix)
        shared = [
            model.is_latest.is_(True),
            or_(model.project_id.is_not(None), model.product_id.is_not(None)),
        ]
        base = select(model).where(*shared, _contains(idents + secondaries, contains))
        total, ranked, fuzzy = await self._ranked_with_fuzzy(
            model, base, rank, term, limit, live=shared, similar=idents + secondaries
        )
        hits = [_map_document(r, resource, _RANK_TO_KIND[rank_val]) for r, rank_val in ranked]
        hits += [_map_document(r, resource, "fuzzy") for (r,) in fuzzy]
        return SearchGroup(resource=resource, total=total, items=hits)

    async def _meetings(self, term: str, limit: int) -> SearchGroup:
        """Meetings not deleted, by their number first and their name
        second. Every signed-in user reads every meeting."""
        t, contains, prefix = _patterns(term)
        idents: list[_TextColumn] = [MeetingOrmModel.meeting_number]
        secondaries: list[_TextColumn] = [MeetingOrmModel.name]
        rank = _identifier_rank(idents, t, prefix)
        live = [MeetingOrmModel.deleted.is_(False)]
        base = select(MeetingOrmModel).where(*live, _contains(idents + secondaries, contains))
        total, ranked, fuzzy = await self._ranked_with_fuzzy(
            MeetingOrmModel, base, rank, term, limit, live=live, similar=idents + secondaries
        )
        hits = [_map_meeting(r, _RANK_TO_KIND[rank_val]) for r, rank_val in ranked]
        hits += [_map_meeting(r, "fuzzy") for (r,) in fuzzy]
        return SearchGroup(resource=LiveResource.MEETINGS, total=total, items=hits)

    async def search_contacts(self, term: str, limit: int) -> SearchGroup:
        """Live contacts by name first, then by e-mail address and the name
        of their customer or supplier. The caller has checked that the
        reader may read contacts."""
        t, contains, prefix = _patterns(term)
        customer = aliased(CustomerOrmModel)
        supplier = aliased(SupplierOrmModel)
        organisation = func.coalesce(customer.name, supplier.name)
        idents: list[_TextColumn] = [ContactOrmModel.name]
        secondaries: list[_TextColumn] = [ContactOrmModel.email, customer.name, supplier.name]
        rank = _identifier_rank(idents, t, prefix)
        live = [ContactOrmModel.archived.is_(False)]
        base = (
            select(ContactOrmModel)
            .outerjoin(customer, ContactOrmModel.customer_id == customer.id)
            .outerjoin(supplier, ContactOrmModel.supplier_id == supplier.id)
            .where(*live, _contains(idents + secondaries, contains))
        )
        total, ranked, fuzzy = await self._ranked_with_fuzzy(
            ContactOrmModel,
            base,
            rank,
            term,
            limit,
            live=live,
            similar=idents,
            columns=[organisation.label("organisation")],
        )
        hits = [
            _map_contact(r, organisation_name, _RANK_TO_KIND[rank_val])
            for r, rank_val, organisation_name in ranked
        ]
        hits += [_map_contact(r, None, "fuzzy") for (r,) in fuzzy]
        return SearchGroup(resource=CONTACT_SEARCH_RESOURCE, total=total, items=hits)

    async def _production_orders(self, term: str, limit: int) -> SearchGroup:
        t, contains, prefix = _patterns(term)
        idents: list[_TextColumn] = [ProductionOrderOrmModel.production_order_number]
        secondaries: list[_TextColumn] = [ProductionOrderOrmModel.note]
        related = _production_order_related(contains)
        via_kind = _production_order_via_kind(contains)
        rank = _rank_with_related(idents, secondaries, t, prefix, contains, related)
        lot_position = selectinload(ProductionOrderOrmModel.lot_position)
        lot = lot_position.selectinload(LotPositionOrmModel.lot)
        made_item = lot.selectinload(ProductionLotOrmModel.made_item)
        detail_options = (
            made_item,
            selectinload(ProductionOrderOrmModel.machine),
            selectinload(ProductionOrderOrmModel.machine_pool),
        )
        # `related`/`via_kind` reference ProductionLotOrmModel columns
        # directly (the "its lot" rule), so the lot has to be joined into
        # the query, not just eager-loaded. Both joins are many-to-one
        # (lot_position_id is a plain FK, lot_id is NOT NULL), so this
        # cannot fan out rows.
        base = (
            select(ProductionOrderOrmModel)
            .join(
                LotPositionOrmModel,
                ProductionOrderOrmModel.lot_position_id == LotPositionOrmModel.id,
            )
            .join(ProductionLotOrmModel, LotPositionOrmModel.lot_id == ProductionLotOrmModel.id)
            .where(or_(_contains(idents + secondaries, contains), related))
        )
        total, ranked, fuzzy = await self._ranked_with_fuzzy(
            ProductionOrderOrmModel,
            base,
            rank,
            term,
            limit,
            live=[],
            similar=idents,
            columns=[via_kind.label("via_kind")],
            options=detail_options,
        )
        hits = [
            _map_production_order(
                r, _RANK_TO_KIND[rank_val], via_kind_val if rank_val == 3 else None
            )
            for r, rank_val, via_kind_val in ranked
        ]
        hits += [_map_production_order(r, "fuzzy", None) for (r,) in fuzzy]
        return SearchGroup(resource=LiveResource.PRODUCTION_ORDERS, total=total, items=hits)
