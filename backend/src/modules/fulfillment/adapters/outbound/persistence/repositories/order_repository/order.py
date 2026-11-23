"""
Concrete SQLAlchemy implementation for the Order aggregate.
"""

from collections.abc import Callable
from datetime import date
from datetime import datetime
from datetime import tzinfo
from typing import Any

from sqlalchemy import ColumnElement
from sqlalchemy import and_
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import QueryableAttribute
from sqlalchemy.orm import selectinload

from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model import (
    BoughtItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.made_item_model import (
    MadeItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.source_item_model import (
    SourceItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.supplier_model import (
    SupplierOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_demand_item_model import (
    BoughtItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model import (
    LotPositionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_extra_cost_model import (
    OrderExtraCostOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_file_model import (
    OrderFileOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_model import OrderOrmModel
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories._lifecycle_rows import (
    ids_after,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories._lifecycle_rows import (
    lock_rows,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository._mappers import (
    order_entity_to_dict,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository._mappers import (
    order_extra_cost_entity_to_dict,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository._mappers import (
    order_load_options,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository._mappers import (
    order_orm_to_entity,
)
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_extra_cost import OrderExtraCost
from src.modules.fulfillment.domain.services.extra_cost_rules import PricedLine
from src.modules.fulfillment.domain.services.extra_cost_rules import signed_amount
from src.modules.fulfillment.domain.value_objects.order_file_category import OrderFileCategory
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.ports.outbound.repositories.order_repository import OrderFilterDto
from src.modules.fulfillment.ports.outbound.repositories.order_repository import OrderSpendFacts
from src.modules.platform.adapters.outbound.persistence.date_range import day_after_utc
from src.modules.platform.adapters.outbound.persistence.date_range import day_start_utc
from src.modules.platform.adapters.outbound.persistence.like_escape import contains_ci
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.number_counters import NumberFamily
from src.modules.platform.adapters.outbound.persistence.number_counters import draw_number
from src.modules.platform.adapters.outbound.persistence.query_filters import FilterSpec
from src.modules.platform.adapters.outbound.persistence.query_filters import apply_filters
from src.modules.platform.adapters.outbound.persistence.query_filters import when
from src.modules.platform.adapters.outbound.persistence.query_filters import when_not_none
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.adapters.outbound.persistence.statements import fetch_page
from src.modules.platform.adapters.outbound.persistence.statements import order_term
from src.modules.platform.adapters.outbound.persistence.tenant_zone import date_filter_zone
from src.modules.platform.domain.exceptions import ConcurrentModificationError
from src.modules.workspace.adapters.outbound.persistence.mappers.product_projects import (
    in_product_projects,
)
from src.modules.workspace.api import ProjectCostBySupplierRow
from src.modules.workspace.api import ProjectSummaryRow

# ══════════════════════════════════════════════════════════════════════
# Order repository
# ══════════════════════════════════════════════════════════════════════

_SORT_COLUMNS: dict[str, Any] = {
    "id": OrderOrmModel.id,
    "order_number": OrderOrmModel.order_number,
    "ordered_date": OrderOrmModel.ordered_date,
    "expected_delivery_date": OrderOrmModel.expected_delivery_date,
    "created": OrderOrmModel.created,
}


def _todo_candidate(horizon: date, zone: tzinfo) -> ColumnElement[bool]:
    """The orders the Todo page can turn into a task: one still to submit,
    and one with an open line that is ready or expected for pickup, partly
    delivered, or expected by `horizon`, a day in `zone`. The page decides
    the bucket and whether a late delivery is a task, so this only keeps
    out the orders that can never give one."""
    line = OrderItemOrmModel
    open_line_needs_action = (
        select(line.id)
        .where(
            line.order_id == OrderOrmModel.id,
            line.status.notin_([OrderItemStatus.DELIVERED.value, OrderItemStatus.CANCELED.value]),
            or_(
                line.ready_for_pickup_date < day_after_utc(horizon, zone),
                line.expected_pickup_date <= horizon,
                and_(line.quantity_delivered > 0, line.quantity_delivered < line.quantity),
                line.expected_delivery_date <= horizon,
            ),
        )
        .exists()
    )
    return or_(
        OrderOrmModel.status.in_(
            [
                OrderStatus.DRAFT.value,
                OrderStatus.REQUESTED.value,
                OrderStatus.PARTIALLY_ORDERED.value,
            ]
        ),
        open_line_needs_action,
    )


class SqlAlchemyOrderRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _reload(self, id: int) -> OrderOrmModel:
        """Re-selects a just-written row with everything the mapper reads.
        populate_existing re-reads every column, so server defaults arrive as
        with refresh(), and applies the loader options to the object already
        in the identity map."""
        return (
            await self._db.scalars(by_id(OrderOrmModel, id, *order_load_options(), refresh=True))
        ).one()

    async def get_by_id(self, id: int) -> Order | None:
        orm = await self._db.scalar(by_id(OrderOrmModel, id, *order_load_options()).limit(1))
        return order_orm_to_entity(orm) if orm else None

    async def get_by_id_for_update(self, id: int) -> Order | None:
        orm = await self._db.scalar(
            by_id(OrderOrmModel, id, *order_load_options(), for_update=True, refresh=True).limit(1)
        )
        return order_orm_to_entity(orm) if orm else None

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[Order]:
        if not ids:
            return []
        rows = (
            await self._db.scalars(
                select(OrderOrmModel)
                .options(*order_load_options())
                .where(OrderOrmModel.id.in_(ids))
                .execution_options(populate_existing=refresh)
            )
        ).all()
        return [order_orm_to_entity(r) for r in rows]

    async def lock_for_update(self, ids: list[int]) -> None:
        await lock_rows(self._db, OrderOrmModel, OrderOrmModel.id, ids)

    async def get_ids_after(self, after_id: int, limit: int) -> list[int]:
        return await ids_after(self._db, OrderOrmModel.id, after_id, limit)

    async def get_by_order_number(self, order_number: str) -> Order | None:
        orm = await self._db.scalar(
            select(OrderOrmModel)
            .options(*order_load_options())
            .where(OrderOrmModel.order_number == order_number)
            .limit(1)
        )
        return order_orm_to_entity(orm) if orm else None

    def _has_invoice_clause(self, has_invoice: bool) -> ColumnElement[bool]:
        invoice_exists = (
            select(OrderFileOrmModel.id)
            .where(
                OrderFileOrmModel.order_id == OrderOrmModel.id,
                OrderFileOrmModel.category == OrderFileCategory.INVOICE.value,
            )
            .exists()
        )
        return invoice_exists if has_invoice else ~invoice_exists

    def _bought_item_clause(self, bought_item_id: int) -> ColumnElement[bool]:
        return OrderOrmModel.id.in_(
            select(OrderItemOrmModel.order_id).where(
                OrderItemOrmModel.bought_item_id == bought_item_id
            )
        )

    def _source_item_clause(self, source_item_id: int) -> ColumnElement[bool]:
        return OrderOrmModel.id.in_(
            select(OrderItemOrmModel.order_id).where(
                OrderItemOrmModel.source_item_id == source_item_id
            )
        )

    def _made_item_clause(self, made_item_id: int) -> ColumnElement[bool]:
        """A MADE line has no made_item_id column of its own, its identity is
        reached through lot_position -> production_lot, the same chain the
        search clause below already walks."""
        return OrderOrmModel.id.in_(
            select(OrderItemOrmModel.order_id)
            .join(
                LotPositionOrmModel,
                OrderItemOrmModel.lot_position_id == LotPositionOrmModel.id,
            )
            .join(
                ProductionLotOrmModel,
                LotPositionOrmModel.lot_id == ProductionLotOrmModel.id,
            )
            .where(ProductionLotOrmModel.made_item_id == made_item_id)
        )

    def _project_clause(self, project_id: int) -> ColumnElement[bool]:
        return OrderOrmModel.id.in_(
            select(OrderItemOrmModel.order_id).where(OrderItemOrmModel.project_id == project_id)
        )

    def _product_clause(self, product_id: int) -> ColumnElement[bool]:
        return OrderOrmModel.id.in_(
            select(OrderItemOrmModel.order_id).where(
                in_product_projects(OrderItemOrmModel.project_id, product_id)
            )
        )

    def _search_clause(self, search: str) -> ColumnElement[bool]:
        term = f"%{search}%"
        # One branch per line type, a line's name lives with its own
        # catalogue row (MADE via lot_position → lot → made_item), and
        # only VIRTUAL lines carry their name on the order item itself.
        matching_order_ids = (
            select(OrderItemOrmModel.order_id)
            .outerjoin(
                BoughtItemOrmModel,
                OrderItemOrmModel.bought_item_id == BoughtItemOrmModel.id,
            )
            .outerjoin(
                SourceItemOrmModel,
                OrderItemOrmModel.source_item_id == SourceItemOrmModel.id,
            )
            .outerjoin(
                LotPositionOrmModel,
                OrderItemOrmModel.lot_position_id == LotPositionOrmModel.id,
            )
            .outerjoin(
                ProductionLotOrmModel,
                LotPositionOrmModel.lot_id == ProductionLotOrmModel.id,
            )
            .outerjoin(
                MadeItemOrmModel,
                ProductionLotOrmModel.made_item_id == MadeItemOrmModel.id,
            )
            .where(
                or_(
                    BoughtItemOrmModel.order_code_1.ilike(term),
                    BoughtItemOrmModel.article_name.ilike(term),
                    SourceItemOrmModel.dimension.ilike(term),
                    SourceItemOrmModel.material.ilike(term),
                    SourceItemOrmModel.order_code_1.ilike(term),
                    SourceItemOrmModel.order_code_2.ilike(term),
                    MadeItemOrmModel.article_name.ilike(term),
                    ProductionLotOrmModel.lot_number.ilike(term),
                    OrderItemOrmModel.virtual_name.ilike(term),
                )
            )
        )
        # The supplier's name too, which the order pickers show beside the
        # number.
        matching_supplier_ids = select(SupplierOrmModel.id).where(SupplierOrmModel.name.ilike(term))
        return or_(
            OrderOrmModel.order_number.ilike(term),
            OrderOrmModel.supplier_order_numbers.ilike(term),
            OrderOrmModel.supplier_id.in_(matching_supplier_ids),
            OrderOrmModel.id.in_(matching_order_ids),
        )

    def _filter_specs(self, filters: OrderFilterDto, zone: tzinfo) -> list[FilterSpec]:
        # Timestamp columns: half-open bounds over days in `zone`, the
        # tenant's, so the `_to` day is included in full rather than cut off
        # at midnight (see date_range.py).
        # expected_delivery_date is a plain calendar date, compared as-is.
        return [
            when(filters.ids, lambda ids: OrderOrmModel.id.in_(ids)),
            when(filters.status, lambda status: OrderOrmModel.status.in_(status)),
            when(filters.supplier_id, lambda supplier_id: OrderOrmModel.supplier_id == supplier_id),
            when(filters.creator_id, lambda creator_id: OrderOrmModel.creator_id == creator_id),
            when(
                filters.changed_by_id,
                lambda changed_by_id: OrderOrmModel.changed_by_id == changed_by_id,
            ),
            when_not_none(
                filters.has_invoice, lambda has_invoice: self._has_invoice_clause(has_invoice)
            ),
            when(
                filters.ordered_from,
                lambda ordered_from: (
                    OrderOrmModel.ordered_date >= day_start_utc(ordered_from, zone)
                ),
            ),
            when(
                filters.ordered_to,
                lambda ordered_to: OrderOrmModel.ordered_date < day_after_utc(ordered_to, zone),
            ),
            when(
                filters.expected_delivery_from,
                lambda expected_delivery_from: (
                    OrderOrmModel.expected_delivery_date >= expected_delivery_from
                ),
            ),
            when(
                filters.expected_delivery_to,
                lambda expected_delivery_to: (
                    OrderOrmModel.expected_delivery_date <= expected_delivery_to
                ),
            ),
            when(
                filters.delivered_from,
                lambda delivered_from: (
                    OrderOrmModel.delivery_date >= day_start_utc(delivered_from, zone)
                ),
            ),
            when(
                filters.delivered_to,
                lambda delivered_to: (
                    OrderOrmModel.delivery_date < day_after_utc(delivered_to, zone)
                ),
            ),
            when(
                filters.created_from,
                lambda created_from: OrderOrmModel.created >= day_start_utc(created_from, zone),
            ),
            when(
                filters.created_to,
                lambda created_to: OrderOrmModel.created < day_after_utc(created_to, zone),
            ),
            when(
                filters.bought_item_id,
                lambda bought_item_id: self._bought_item_clause(bought_item_id),
            ),
            when(
                filters.source_item_id,
                lambda source_item_id: self._source_item_clause(source_item_id),
            ),
            when(filters.made_item_id, lambda made_item_id: self._made_item_clause(made_item_id)),
            when(filters.project_id, lambda project_id: self._project_clause(project_id)),
            when(filters.product_id, lambda product_id: self._product_clause(product_id)),
            # The number filter matches the supplier's numbers for the order
            # too, which the orders table shows under the order number.
            when(
                filters.order_number,
                lambda order_number: or_(
                    contains_ci(OrderOrmModel.order_number, order_number),
                    contains_ci(OrderOrmModel.supplier_order_numbers, order_number),
                ),
            ),
            when(filters.note, lambda note: contains_ci(OrderOrmModel.note, note)),
            when(
                filters.storage_place,
                lambda storage_place: contains_ci(OrderOrmModel.storage_place, storage_place),
            ),
            when(filters.search, lambda search: self._search_clause(search)),
            when(filters.todo_horizon, lambda horizon: _todo_candidate(horizon, zone)),
        ]

    async def get_spend_facts(
        self, ordered_from: datetime, ordered_before: datetime
    ) -> list[OrderSpendFacts]:
        orders = (
            await self._db.execute(
                select(OrderOrmModel.id, OrderOrmModel.ordered_date).where(
                    OrderOrmModel.ordered_date >= ordered_from,
                    OrderOrmModel.ordered_date < ordered_before,
                )
            )
        ).all()
        facts = {
            order_id: OrderSpendFacts(ordered_date=utc_aware(ordered_date))
            for order_id, ordered_date in orders
            if ordered_date is not None
        }
        if not facts:
            return []
        lines = await self._db.execute(
            select(
                OrderItemOrmModel.order_id,
                OrderItemOrmModel.price,
                OrderItemOrmModel.quantity,
                OrderItemOrmModel.canceled_at,
            ).where(OrderItemOrmModel.order_id.in_(facts))
        )
        for order_id, price, quantity, canceled_at in lines.tuples():
            facts[order_id].lines.append(
                PricedLine(price=price, quantity=quantity, canceled=canceled_at is not None)
            )
        costs = await self._db.execute(
            select(
                OrderExtraCostOrmModel.order_id,
                OrderExtraCostOrmModel.kind,
                OrderExtraCostOrmModel.amount,
            ).where(OrderExtraCostOrmModel.order_id.in_(facts))
        )
        for order_id, kind, amount in costs.tuples():
            facts[order_id].extra_costs.append((kind, amount))
        return list(facts.values())

    async def get_multi(self, filters: OrderFilterDto) -> tuple[int, list[Order]]:
        q = select(OrderOrmModel)
        zone = await date_filter_zone(
            self._db,
            filters.ordered_from,
            filters.ordered_to,
            filters.delivered_from,
            filters.delivered_to,
            filters.created_from,
            filters.created_to,
        )
        q = apply_filters(q, self._filter_specs(filters, zone))

        sort_col = _SORT_COLUMNS.get(filters.order_by or "id", OrderOrmModel.id)
        total, rows = await fetch_page(
            self._db,
            q,
            filters.skip,
            filters.limit,
            order_term(sort_col, filters.order_dir, default="desc"),
            options=order_load_options(),
            min_limit=len(filters.ids) if filters.ids else None,
        )
        return total, [order_orm_to_entity(r) for r in rows]

    async def get_project_summary(self, project_id: int) -> ProjectSummaryRow:
        return await self._summary(lambda column: column == project_id)

    async def get_product_summary(self, product_id: int) -> ProjectSummaryRow:
        return await self._summary(lambda column: in_product_projects(column, product_id))

    async def _summary(
        self, in_scope: Callable[[QueryableAttribute[Any]], ColumnElement[bool]]
    ) -> ProjectSummaryRow:
        """Order cost and demand status rollup over the projects that
        `in_scope` accepts, extra costs included in the ordered cost (see
        _extra_costs_in_scope), given the project id column of the table being
        summed. An order with items for several projects in scope is counted
        once per supplier, not once per project."""
        supplier_rows = (
            await self._db.execute(
                select(
                    OrderItemOrmModel.supplier_id,
                    SupplierOrmModel.name.label("supplier_name"),
                    func.sum(OrderItemOrmModel.price * OrderItemOrmModel.quantity).label(
                        "ordered_cost"
                    ),
                    func.sum(OrderItemOrmModel.price * OrderItemOrmModel.quantity_delivered).label(
                        "delivered_cost"
                    ),
                    func.count(func.distinct(OrderItemOrmModel.order_id)).label("order_count"),
                )
                .join(SupplierOrmModel, SupplierOrmModel.id == OrderItemOrmModel.supplier_id)
                .where(
                    in_scope(OrderItemOrmModel.project_id),
                    OrderItemOrmModel.price.isnot(None),
                )
                .group_by(
                    OrderItemOrmModel.supplier_id,
                    SupplierOrmModel.name,
                )
            )
        ).all()

        status_rows = (
            await self._db.execute(
                select(BoughtItemDemandItemOrmModel.status, func.count().label("cnt"))
                .where(in_scope(BoughtItemDemandItemOrmModel.project_id))
                .group_by(BoughtItemDemandItemOrmModel.status)
            )
        ).all()

        by_supplier: dict[int, ProjectCostBySupplierRow] = {
            r.supplier_id: {
                "supplier_id": r.supplier_id,
                "supplier_name": r.supplier_name,
                "ordered_cost": int(r.ordered_cost or 0),
                "delivered_cost": int(r.delivered_cost or 0),
            }
            for r in supplier_rows
        }
        for supplier_id, supplier_name, cost in await self._extra_costs_in_scope(in_scope):
            row = by_supplier.setdefault(
                supplier_id,
                {
                    "supplier_id": supplier_id,
                    "supplier_name": supplier_name,
                    "ordered_cost": 0,
                    "delivered_cost": 0,
                },
            )
            row["ordered_cost"] += cost
        order_count = sum(r.order_count for r in supplier_rows)

        return {
            "total_ordered_cost": sum(r["ordered_cost"] for r in by_supplier.values()),
            "total_delivered_cost": sum(r["delivered_cost"] for r in by_supplier.values()),
            "order_count": order_count,
            "cost_by_supplier": list(by_supplier.values()),
            "demand_counts": {row.status: row.cnt for row in status_rows},
        }

    async def _extra_costs_in_scope(
        self, in_scope: Callable[[QueryableAttribute[Any]], ColumnElement[bool]]
    ) -> list[tuple[int, str, int]]:
        """The share of each order's extra costs that falls on the projects
        `in_scope` accepts, as (supplier id, supplier name, cents), discounts
        negative. A cost of one line counts in full for that line's project.
        A cost of the whole order is shared by line value: the part of it the
        order's lines in scope make up, or by line count where no line of
        the order carries a price. Delivered costs count goods only."""
        line_value = func.coalesce(OrderItemOrmModel.price, 0) * OrderItemOrmModel.quantity
        scoped = (
            await self._db.execute(
                select(
                    OrderItemOrmModel.order_id,
                    func.sum(line_value).label("value"),
                    func.count().label("lines"),
                )
                .where(in_scope(OrderItemOrmModel.project_id))
                .group_by(OrderItemOrmModel.order_id)
            )
        ).all()
        if not scoped:
            return []
        order_ids = [r.order_id for r in scoped]
        totals = {
            r.order_id: (float(r.value or 0), int(r.lines))
            for r in (
                await self._db.execute(
                    select(
                        OrderItemOrmModel.order_id,
                        func.sum(line_value).label("value"),
                        func.count().label("lines"),
                    )
                    .where(OrderItemOrmModel.order_id.in_(order_ids))
                    .group_by(OrderItemOrmModel.order_id)
                )
            ).all()
        }
        scoped_lines = set(
            (
                await self._db.scalars(
                    select(OrderItemOrmModel.id).where(
                        OrderItemOrmModel.order_id.in_(order_ids),
                        in_scope(OrderItemOrmModel.project_id),
                    )
                )
            ).all()
        )
        costs = (
            await self._db.execute(
                select(
                    OrderExtraCostOrmModel.order_id,
                    OrderExtraCostOrmModel.order_item_id,
                    OrderExtraCostOrmModel.kind,
                    OrderExtraCostOrmModel.amount,
                    OrderOrmModel.supplier_id,
                    SupplierOrmModel.name,
                )
                .join(OrderOrmModel, OrderOrmModel.id == OrderExtraCostOrmModel.order_id)
                .join(SupplierOrmModel, SupplierOrmModel.id == OrderOrmModel.supplier_id)
                .where(OrderExtraCostOrmModel.order_id.in_(order_ids))
            )
        ).all()
        share = {
            r.order_id: (
                float(r.value or 0) / totals[r.order_id][0]
                if totals[r.order_id][0] > 0
                else int(r.lines) / max(totals[r.order_id][1], 1)
            )
            for r in scoped
        }
        result: list[tuple[int, str, int]] = []
        for order_id, line_id, kind, amount, supplier_id, supplier_name in costs:
            signed = signed_amount(kind, amount)
            if line_id is not None:
                if line_id in scoped_lines:
                    result.append((supplier_id, supplier_name, signed))
                continue
            result.append((supplier_id, supplier_name, round(signed * share[order_id])))
        return result

    async def save(self, order: Order) -> Order:
        if order.id == 0:
            orm = OrderOrmModel(**order_entity_to_dict(order))
            self._db.add(orm)
            await self._db.flush()
            return order_orm_to_entity(await self._reload(orm.id))
        existing = await self._db.get(OrderOrmModel, order.id)
        if not existing:
            raise ConcurrentModificationError(
                f"OrderOrmModel id={order.id} was removed"
                " while this request worked on it; reload and try again."
            )
        orm = existing
        for k, v in order_entity_to_dict(order).items():
            setattr(orm, k, v)
        await self._db.flush()
        return order_orm_to_entity(await self._reload(orm.id))

    async def set_extra_costs(self, order_id: int, costs: list[OrderExtraCost]) -> None:
        orm = await self._db.scalar(
            select(OrderOrmModel)
            .where(OrderOrmModel.id == order_id)
            .options(selectinload(OrderOrmModel.extra_costs))
        )
        if orm is None:
            raise ConcurrentModificationError(
                f"OrderOrmModel id={order_id} was removed"
                " while this request worked on it; reload and try again."
            )
        orm.extra_costs = [
            OrderExtraCostOrmModel(**order_extra_cost_entity_to_dict(c)) for c in costs
        ]
        await self._db.flush()

    async def delete(self, order: Order) -> None:
        # The unit of work dereferences the child collections on delete, so
        # they are loaded with the row rather than lazily during flush.
        orm = await self._db.scalar(
            select(OrderOrmModel)
            .where(OrderOrmModel.id == order.id)
            .options(
                selectinload(OrderOrmModel.order_items),
                selectinload(OrderOrmModel.files),
                selectinload(OrderOrmModel.extra_costs),
            )
        )
        if orm:
            await self._db.delete(orm)
            await self._db.flush()

    async def next_order_number(self, template: str) -> str:
        """Draws the next order number per the admin-configured template
        (see src.modules.platform.domain.services.numbering_format) from the order counter
        (persistence/number_counters.py)."""
        return await draw_number(
            self._db,
            NumberFamily.ORDER,
            template,
            column=OrderOrmModel.order_number,
        )
