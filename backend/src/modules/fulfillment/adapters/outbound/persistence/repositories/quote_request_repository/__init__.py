"""
Concrete SQLAlchemy implementation of the quote request (RFQ) aggregate.

The request is read as a whole, with its lines, demand shares, suppliers,
offers and offer extra costs. Each part is written on its own: the request's
fields, one line with its shares, one supplier row, and one supplier's offer
as a whole. A part is written through the request's loaded collections, so
the request read back in the same session sees it.
"""

from sqlalchemy import ColumnElement
from sqlalchemy import and_
from sqlalchemy import exists
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.quote_request_model import (
    QuoteRequestLineDemandOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.quote_request_model import (
    QuoteRequestLineOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.quote_request_model import (
    QuoteRequestOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.quote_request_model import (
    QuoteRequestSupplierOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories._lifecycle_rows import (
    ids_after,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories._lifecycle_rows import (
    lock_rows,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.quote_request_repository._cleanup import (
    delete_quote_request_lines,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.quote_request_repository._mappers import (
    cost_entity_to_orm,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.quote_request_repository._mappers import (
    demand_entity_to_orm,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.quote_request_repository._mappers import (
    line_entity_to_dict,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.quote_request_repository._mappers import (
    line_orm_to_entity,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.quote_request_repository._mappers import (
    quote_entity_to_orm,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.quote_request_repository._mappers import (
    quote_request_entity_to_dict,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.quote_request_repository._mappers import (
    quote_request_load_options,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.quote_request_repository._mappers import (
    quote_request_orm_to_entity,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.quote_request_repository._mappers import (
    supplier_entity_to_dict,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.quote_request_repository._mappers import (
    supplier_orm_to_entity,
)
from src.modules.fulfillment.domain.entities.quote_request import Quote
from src.modules.fulfillment.domain.entities.quote_request import QuoteExtraCost
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequest
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequestLine
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequestSupplier
from src.modules.fulfillment.domain.value_objects.quote_request_status import (
    QuoteRequestDemandFamily,
)
from src.modules.fulfillment.domain.value_objects.quote_request_status import QuoteRequestStatus
from src.modules.fulfillment.ports.outbound.repositories.quote_request_repository import (
    OpenQuoteRequestLinks,
)
from src.modules.fulfillment.ports.outbound.repositories.quote_request_repository import (
    OpenQuoteRequestRef,
)
from src.modules.fulfillment.ports.outbound.repositories.quote_request_repository import (
    QuoteRequestFilterDto,
)
from src.modules.platform.adapters.outbound.persistence.like_escape import contains_ci
from src.modules.platform.adapters.outbound.persistence.number_counters import NumberFamily
from src.modules.platform.adapters.outbound.persistence.number_counters import draw_number
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.adapters.outbound.persistence.statements import fetch_page
from src.modules.platform.adapters.outbound.persistence.statements import order_term
from src.modules.platform.domain.exceptions import ConcurrentModificationError

_SORT_COLUMNS = {
    "id": QuoteRequestOrmModel.id,
    "request_number": QuoteRequestOrmModel.request_number,
    "created": QuoteRequestOrmModel.created,
    "deadline": QuoteRequestOrmModel.deadline,
    "status": QuoteRequestOrmModel.status,
}

_OPEN_STATUSES = (QuoteRequestStatus.DRAFT.value, QuoteRequestStatus.SENT.value)


def open_line_condition() -> ColumnElement[bool]:
    """The SQL condition of a line in the OPEN state, as QuoteRequestLine.state
    derives it: not dropped, and either never awarded or awarded with no
    order line of the award live any more, which voids the award."""
    live_award_line = exists().where(
        OrderItemOrmModel.quote_request_line_id == QuoteRequestLineOrmModel.id,
        OrderItemOrmModel.canceled_at.is_(None),
    )
    return and_(
        or_(QuoteRequestLineOrmModel.awarded_at.is_(None), ~live_award_line),
        QuoteRequestLineOrmModel.dropped_at.is_(None),
    )


def _gone(model: str, id: int) -> ConcurrentModificationError:
    return ConcurrentModificationError(
        f"{model} id={id} was removed while this request worked on it; reload and try again."
    )


class SqlAlchemyQuoteRequestRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _reload(self, id: int) -> QuoteRequestOrmModel:
        return (
            await self._db.scalars(
                by_id(QuoteRequestOrmModel, id, *quote_request_load_options(), refresh=True)
            )
        ).one()

    async def get_by_id(self, id: int) -> QuoteRequest | None:
        orm = await self._db.scalar(
            by_id(QuoteRequestOrmModel, id, *quote_request_load_options(), refresh=True).limit(1)
        )
        return quote_request_orm_to_entity(orm) if orm else None

    async def get_by_id_for_update(self, id: int) -> QuoteRequest | None:
        orm = await self._db.scalar(
            by_id(
                QuoteRequestOrmModel,
                id,
                *quote_request_load_options(),
                for_update=True,
                refresh=True,
            ).limit(1)
        )
        return quote_request_orm_to_entity(orm) if orm else None

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[QuoteRequest]:
        if not ids:
            return []
        rows = (
            await self._db.scalars(
                select(QuoteRequestOrmModel)
                .options(*quote_request_load_options())
                .where(QuoteRequestOrmModel.id.in_(ids))
                .execution_options(populate_existing=refresh)
            )
        ).all()
        return [quote_request_orm_to_entity(r) for r in rows]

    async def lock_for_update(self, ids: list[int]) -> None:
        await lock_rows(self._db, QuoteRequestOrmModel, QuoteRequestOrmModel.id, ids)

    async def get_ids_after(self, after_id: int, limit: int) -> list[int]:
        return await ids_after(self._db, QuoteRequestOrmModel.id, after_id, limit)

    def _filters(self, filters: QuoteRequestFilterDto) -> list[ColumnElement[bool]]:
        clauses: list[ColumnElement[bool]] = []
        if filters.ids:
            clauses.append(QuoteRequestOrmModel.id.in_(filters.ids))
        if filters.status:
            clauses.append(QuoteRequestOrmModel.status.in_(filters.status))
        if filters.creator_id is not None:
            clauses.append(QuoteRequestOrmModel.creator_id == filters.creator_id)
        if filters.supplier_id is not None:
            clauses.append(
                QuoteRequestOrmModel.suppliers.any(
                    QuoteRequestSupplierOrmModel.supplier_id == filters.supplier_id
                )
            )
        if filters.search:
            term = filters.search.strip()
            clauses.append(
                or_(
                    contains_ci(QuoteRequestOrmModel.request_number, term),
                    contains_ci(QuoteRequestOrmModel.note, term),
                )
            )
        return clauses

    async def get_multi(self, filters: QuoteRequestFilterDto) -> tuple[int, list[QuoteRequest]]:
        stmt = select(QuoteRequestOrmModel).where(*self._filters(filters))
        sort_col = _SORT_COLUMNS.get(filters.order_by or "id", QuoteRequestOrmModel.id)
        total, rows = await fetch_page(
            self._db,
            stmt,
            filters.skip,
            filters.limit,
            order_term(sort_col, filters.order_dir, default="desc"),
            options=quote_request_load_options(),
            min_limit=len(filters.ids) if filters.ids else None,
        )
        return total, [quote_request_orm_to_entity(r) for r in rows]

    async def save(self, request: QuoteRequest) -> QuoteRequest:
        if request.id == 0:
            orm = QuoteRequestOrmModel(**quote_request_entity_to_dict(request))
            orm.lines = []
            orm.suppliers = []
            self._db.add(orm)
            await self._db.flush()
            return quote_request_orm_to_entity(await self._reload(orm.id))
        existing = await self._db.get(QuoteRequestOrmModel, request.id)
        if existing is None:
            raise _gone("QuoteRequestOrmModel", request.id)
        for key, value in quote_request_entity_to_dict(request).items():
            setattr(existing, key, value)
        await self._db.flush()
        return quote_request_orm_to_entity(await self._reload(existing.id))

    async def _line_orm(self, line_id: int) -> QuoteRequestLineOrmModel | None:
        found: QuoteRequestLineOrmModel | None = await self._db.scalar(
            select(QuoteRequestLineOrmModel)
            .where(QuoteRequestLineOrmModel.id == line_id)
            .options(selectinload(QuoteRequestLineOrmModel.demands))
        )
        return found

    async def save_line(self, line: QuoteRequestLine) -> QuoteRequestLine:
        if line.id == 0:
            orm = QuoteRequestLineOrmModel(**line_entity_to_dict(line))
            orm.demands = [demand_entity_to_orm(d) for d in line.demands]
            self._db.add(orm)
        else:
            found = await self._line_orm(line.id)
            if found is None:
                raise _gone("QuoteRequestLineOrmModel", line.id)
            orm = found
            for key, value in line_entity_to_dict(line).items():
                setattr(orm, key, value)
            self._sync_demands(orm, line)
        await self._db.flush()
        request = await self._reload(orm.quote_request_id)
        return line_orm_to_entity(next(row for row in request.lines if row.id == orm.id))

    @staticmethod
    def _sync_demands(orm: QuoteRequestLineOrmModel, line: QuoteRequestLine) -> None:
        """Makes the line's shares the entity's, keeping the rows of the
        demands that stay, so a share is never deleted and inserted again
        under its unique key in one flush."""
        wanted = {(d.family, d.demand_item_id): d for d in line.demands}
        kept = []
        for row in orm.demands:
            key = (
                (QuoteRequestDemandFamily.BOUGHT.value, row.bought_demand_item_id)
                if row.bought_demand_item_id is not None
                else (QuoteRequestDemandFamily.SOURCE.value, row.source_demand_item_id)
            )
            share = wanted.pop(key, None)  # type: ignore[arg-type]
            if share is not None:
                row.quantity = share.quantity
                kept.append(row)
        orm.demands = kept + [demand_entity_to_orm(d) for d in wanted.values()]

    async def delete_line(self, line_id: int) -> None:
        await delete_quote_request_lines(self._db, QuoteRequestLineOrmModel.id == line_id)
        await self._db.flush()

    async def _supplier_orm(self, row_id: int) -> QuoteRequestSupplierOrmModel | None:
        found: QuoteRequestSupplierOrmModel | None = await self._db.scalar(
            select(QuoteRequestSupplierOrmModel)
            .where(QuoteRequestSupplierOrmModel.id == row_id)
            .options(
                selectinload(QuoteRequestSupplierOrmModel.quotes),
                selectinload(QuoteRequestSupplierOrmModel.extra_costs),
            )
        )
        return found

    async def save_supplier(self, row: QuoteRequestSupplier) -> QuoteRequestSupplier:
        if row.id == 0:
            orm = QuoteRequestSupplierOrmModel(**supplier_entity_to_dict(row))
            orm.quotes = []
            orm.extra_costs = []
            self._db.add(orm)
        else:
            found = await self._supplier_orm(row.id)
            if found is None:
                raise _gone("QuoteRequestSupplierOrmModel", row.id)
            orm = found
            for key, value in supplier_entity_to_dict(row).items():
                setattr(orm, key, value)
        await self._db.flush()
        request = await self._reload(orm.quote_request_id)
        return supplier_orm_to_entity(next(r for r in request.suppliers if r.id == orm.id))

    async def delete_supplier(self, row_id: int) -> None:
        orm = await self._supplier_orm(row_id)
        if orm is not None:
            await self._db.delete(orm)
            await self._db.flush()

    async def set_offer(
        self, row_id: int, quotes: list[Quote], extra_costs: list[QuoteExtraCost]
    ) -> None:
        orm = await self._supplier_orm(row_id)
        if orm is None:
            raise _gone("QuoteRequestSupplierOrmModel", row_id)
        # The old rows go in a flush of their own: one flush inserts before
        # it deletes, and a new quote for a line would meet the old one
        # under uq_quote_supplier_row_line.
        orm.quotes = []
        orm.extra_costs = []
        await self._db.flush()
        orm.quotes = [quote_entity_to_orm(q) for q in quotes]
        orm.extra_costs = [cost_entity_to_orm(c) for c in extra_costs]
        await self._db.flush()

    async def next_request_number(self, template: str) -> str:
        """Draws the next quote request number per the admin-configured
        template from the quote request counter."""
        return await draw_number(
            self._db,
            NumberFamily.QUOTE_REQUEST,
            template,
            column=QuoteRequestOrmModel.request_number,
        )

    async def get_open_links(
        self,
        *,
        bought_demand_ids: list[int],
        source_demand_ids: list[int],
        lot_position_ids: list[int],
    ) -> OpenQuoteRequestLinks:
        """The open lines of DRAFT or SENT requests that name the demands or
        positions, each request once per id, in request id order. A line
        whose award is void, because no order line of the award is live any
        more, is open again."""
        links = OpenQuoteRequestLinks()
        open_line = (open_line_condition(), QuoteRequestOrmModel.status.in_(_OPEN_STATUSES))
        demand_columns = (
            (QuoteRequestLineDemandOrmModel.bought_demand_item_id, bought_demand_ids),
            (QuoteRequestLineDemandOrmModel.source_demand_item_id, source_demand_ids),
        )
        for (column, ids), target in zip(
            demand_columns, (links.bought_demands, links.source_demands), strict=True
        ):
            if not ids:
                continue
            rows = await self._db.execute(
                select(column, QuoteRequestOrmModel.id, QuoteRequestOrmModel.request_number)
                .join(
                    QuoteRequestLineOrmModel,
                    QuoteRequestLineOrmModel.id == QuoteRequestLineDemandOrmModel.line_id,
                )
                .join(
                    QuoteRequestOrmModel,
                    QuoteRequestOrmModel.id == QuoteRequestLineOrmModel.quote_request_id,
                )
                .where(column.in_(ids), *open_line)
                .distinct()
                .order_by(QuoteRequestOrmModel.id)
            )
            for demand_id, request_id, number in rows.all():
                target.setdefault(int(demand_id), []).append(
                    OpenQuoteRequestRef(id=request_id, request_number=number)
                )
        if lot_position_ids:
            rows = await self._db.execute(
                select(
                    QuoteRequestLineOrmModel.lot_position_id,
                    QuoteRequestOrmModel.id,
                    QuoteRequestOrmModel.request_number,
                )
                .join(
                    QuoteRequestOrmModel,
                    QuoteRequestOrmModel.id == QuoteRequestLineOrmModel.quote_request_id,
                )
                .where(QuoteRequestLineOrmModel.lot_position_id.in_(lot_position_ids), *open_line)
                .distinct()
                .order_by(QuoteRequestOrmModel.id)
            )
            for position_id, request_id, number in rows.all():
                links.lot_positions.setdefault(int(position_id), []).append(
                    OpenQuoteRequestRef(id=request_id, request_number=number)
                )
        return links
