"""
SQLAlchemy implementation of IProductionKpiRepository: the bounded,
batched queries the production KPI use case needs, each scoped by a
period and the shared machine/pool/project/customer filter. Every method
returns plain rows (kpi_rules.py dataclasses), never ORM rows.
"""

from collections.abc import Sequence
from datetime import datetime
from datetime import tzinfo
from typing import Any
from typing import TypeVar

from sqlalchemy import Row
from sqlalchemy import Select
from sqlalchemy import and_
from sqlalchemy import exists
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from src.modules.catalogue.adapters.outbound.persistence.models.fabrication_method_model import (
    FabricationMethodOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.made_item_model import (
    MadeItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.supplier_model import (
    SupplierOrmModel,
)
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model import (
    LotPositionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_step_model import (
    LotStepOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_delivery_model import (
    OrderItemDeliveryOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_completion_model import (
    ProductionOrderCompletionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model import (
    ProductionOrderOrmModel,
)
from src.modules.fulfillment.domain.entities.production_order_interruption import (
    ProductionOrderInterruption,
)
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.rejection_outcome import RejectionOutcome
from src.modules.fulfillment.ports.outbound.fulfillment_queries import (
    IProductionOrderInterruptionQueries,
)
from src.modules.platform.adapters.outbound.persistence.date_range import day_after_utc
from src.modules.platform.adapters.outbound.persistence.date_range import day_start_utc
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.quality.domain.services.kpi_rules import CompletedOrderRow
from src.modules.quality.domain.services.kpi_rules import CompletionRow
from src.modules.quality.domain.services.kpi_rules import FabricationMethodRef
from src.modules.quality.domain.services.kpi_rules import ScrapReasonRow
from src.modules.quality.domain.services.kpi_rules import SupplierDeliveryRow
from src.modules.quality.domain.services.kpi_rules import WaitingRow
from src.modules.quality.ports.outbound.repositories.production_kpi_repository import (
    CompletedLotRow,
)
from src.modules.quality.ports.outbound.repositories.production_kpi_repository import KpiPeriod
from src.modules.quality.ports.outbound.repositories.production_kpi_repository import KpiScope
from src.modules.quality.ports.outbound.repositories.production_kpi_repository import (
    LateLotCandidateRow,
)
from src.modules.workspace.adapters.outbound.persistence.models.project_model import ProjectOrmModel

_OPEN_LOT_STATUSES = [
    status
    for status in LotStatus.values()
    if status not in (LotStatus.COMPLETED.value, LotStatus.CANCELED.value, LotStatus.SCRAPPED.value)
]


def _machine_scope_exists(scope: KpiScope) -> ColumnElement[bool] | None:
    """An EXISTS(...) clause matching a lot with at least one order on the
    scoped machine/pool, None when neither filter is set. Kept as one
    helper since get_completed_lots and get_late_lot_candidates both need
    it, lot-level KPIs have no order of their own to filter on directly."""
    if scope.machine_id is None and scope.machine_pool_id is None:
        return None
    conditions = [
        LotPositionOrmModel.lot_id == ProductionLotOrmModel.id,
        ProductionOrderOrmModel.lot_position_id == LotPositionOrmModel.id,
    ]
    if scope.machine_id is not None:
        conditions.append(ProductionOrderOrmModel.machine_id == scope.machine_id)
    if scope.machine_pool_id is not None:
        conditions.append(ProductionOrderOrmModel.machine_pool_id == scope.machine_pool_id)
    return exists().where(and_(*conditions))


_Q = TypeVar("_Q", bound="Select[Any]")


def _apply_order_lot_scope(q: _Q, scope: KpiScope) -> _Q:
    """Applies KpiScope's machine/pool/project/customer narrowing to a
    query already joined through ProductionOrderOrmModel and
    ProductionLotOrmModel. Shared by get_waiting_time_rows and the
    completion half of get_scrap_events, the two queries built directly
    against those two tables rather than via _machine_scope_exists's own
    EXISTS subquery."""
    if scope.machine_id is not None:
        q = q.where(ProductionOrderOrmModel.machine_id == scope.machine_id)
    if scope.machine_pool_id is not None:
        q = q.where(ProductionOrderOrmModel.machine_pool_id == scope.machine_pool_id)
    if scope.project_id is not None:
        q = q.where(ProductionLotOrmModel.project_id == scope.project_id)
    if scope.customer_id is not None:
        q = q.join(ProjectOrmModel, ProductionLotOrmModel.project_id == ProjectOrmModel.id)
        q = q.where(ProjectOrmModel.customer_id == scope.customer_id)
    return q


class SqlAlchemyProductionKpiRepository:
    def __init__(
        self, db: AsyncSession, interruption_repo: IProductionOrderInterruptionQueries
    ) -> None:
        self._db = db
        self._interruptions = interruption_repo

    async def get_completed_orders(
        self, period: KpiPeriod, scope: KpiScope
    ) -> list[CompletedOrderRow]:
        q = (
            select(ProductionOrderOrmModel, LotPositionOrmModel.lot_id)
            .join(
                LotPositionOrmModel,
                ProductionOrderOrmModel.lot_position_id == LotPositionOrmModel.id,
            )
            .join(ProductionLotOrmModel, LotPositionOrmModel.lot_id == ProductionLotOrmModel.id)
            .where(
                ProductionOrderOrmModel.status == ProductionOrderStatus.COMPLETED.value,
                ProductionOrderOrmModel.actual_end.isnot(None),
                ProductionOrderOrmModel.actual_end >= day_start_utc(period.date_from, period.zone),
                ProductionOrderOrmModel.actual_end < day_after_utc(period.date_to, period.zone),
            )
        )
        if scope.machine_id is not None:
            q = q.where(ProductionOrderOrmModel.machine_id == scope.machine_id)
        if scope.machine_pool_id is not None:
            q = q.where(ProductionOrderOrmModel.machine_pool_id == scope.machine_pool_id)
        if scope.project_id is not None:
            q = q.where(ProductionLotOrmModel.project_id == scope.project_id)
        if scope.customer_id is not None:
            q = q.join(ProjectOrmModel, ProductionLotOrmModel.project_id == ProjectOrmModel.id)
            q = q.where(ProjectOrmModel.customer_id == scope.customer_id)
        rows = (await self._db.execute(q)).all()
        if not rows:
            return []

        orders = [order for order, _lot_id in rows]
        order_ids = [order.id for order in orders]
        position_ids = {order.lot_position_id for order in orders}

        interruptions_by_order: dict[int, list[ProductionOrderInterruption]] = {}
        for interruption in await self._interruptions.get_by_order_ids(order_ids):
            interruptions_by_order.setdefault(interruption.production_order_id, []).append(
                interruption
            )

        method_rows = (
            await self._db.execute(
                select(
                    LotStepOrmModel.position_id,
                    FabricationMethodOrmModel.id,
                    FabricationMethodOrmModel.name,
                )
                .join(
                    FabricationMethodOrmModel,
                    LotStepOrmModel.fabrication_method_id == FabricationMethodOrmModel.id,
                )
                .where(
                    LotStepOrmModel.position_id.in_(position_ids),
                    LotStepOrmModel.role == StepRole.FABRICATION.value,
                )
            )
        ).all()
        methods_by_position: dict[int, dict[int, LocalizedText]] = {}
        for position_id, method_id, method_name in method_rows:
            methods_by_position.setdefault(position_id, {})[method_id] = LocalizedText(
                values=dict(method_name or {})
            )

        return [
            CompletedOrderRow(
                order_id=order.id,
                machine_id=order.machine_id,
                lot_id=lot_id,
                actual_start=order.actual_start,
                actual_end=order.actual_end,
                planned_end_at_start=order.planned_end_at_start,
                estimated_duration_minutes=order.estimated_duration_minutes,
                interruptions=tuple(interruptions_by_order.get(order.id, [])),
                fabrication_methods=tuple(
                    FabricationMethodRef(id=method_id, name=method_name)
                    for method_id, method_name in methods_by_position.get(
                        order.lot_position_id, {}
                    ).items()
                ),
            )
            for order, lot_id in rows
        ]

    async def get_completions(self, period: KpiPeriod, scope: KpiScope) -> list[CompletionRow]:
        q = (
            select(ProductionOrderCompletionOrmModel, MadeItemOrmModel)
            .join(
                ProductionOrderOrmModel,
                ProductionOrderCompletionOrmModel.production_order_id == ProductionOrderOrmModel.id,
            )
            .join(
                LotPositionOrmModel,
                ProductionOrderOrmModel.lot_position_id == LotPositionOrmModel.id,
            )
            .join(ProductionLotOrmModel, LotPositionOrmModel.lot_id == ProductionLotOrmModel.id)
            .join(MadeItemOrmModel, ProductionLotOrmModel.made_item_id == MadeItemOrmModel.id)
            .where(
                ProductionOrderCompletionOrmModel.completion_date >= period.date_from,
                ProductionOrderCompletionOrmModel.completion_date <= period.date_to,
            )
        )
        if scope.machine_id is not None:
            q = q.where(ProductionOrderOrmModel.machine_id == scope.machine_id)
        if scope.machine_pool_id is not None:
            q = q.where(ProductionOrderOrmModel.machine_pool_id == scope.machine_pool_id)
        if scope.project_id is not None:
            q = q.where(ProductionLotOrmModel.project_id == scope.project_id)
        if scope.customer_id is not None:
            q = q.join(ProjectOrmModel, ProductionLotOrmModel.project_id == ProjectOrmModel.id)
            q = q.where(ProjectOrmModel.customer_id == scope.customer_id)
        rows = (await self._db.execute(q)).all()
        return [
            CompletionRow(
                completion_id=completion.id,
                made_item_id=made_item.id,
                made_item_part_number=made_item.part_number or "",
                made_item_article_name=made_item.article_name,
                quantity=completion.quantity,
                quantity_accepted=completion.quantity_accepted,
                quantity_rejected=completion.quantity_rejected,
                quantity_rework=completion.quantity_rework,
                quantity_scrap=completion.quantity_scrap,
            )
            for completion, made_item in rows
        ]

    async def get_completed_lots(self, period: KpiPeriod, scope: KpiScope) -> list[CompletedLotRow]:
        q = select(ProductionLotOrmModel).where(
            ProductionLotOrmModel.completed_at.isnot(None),
            ProductionLotOrmModel.completed_at >= day_start_utc(period.date_from, period.zone),
            ProductionLotOrmModel.completed_at < day_after_utc(period.date_to, period.zone),
        )
        if scope.project_id is not None:
            q = q.where(ProductionLotOrmModel.project_id == scope.project_id)
        if scope.customer_id is not None:
            q = q.join(ProjectOrmModel, ProductionLotOrmModel.project_id == ProjectOrmModel.id)
            q = q.where(ProjectOrmModel.customer_id == scope.customer_id)
        machine_scope = _machine_scope_exists(scope)
        if machine_scope is not None:
            q = q.where(machine_scope)
        lots = (await self._db.scalars(q)).all()
        rows = []
        for lot in lots:
            if lot.completed_at is None:
                continue
            rows.append(
                CompletedLotRow(
                    lot_id=lot.id,
                    lot_number=lot.lot_number,
                    created=lot.created,
                    completed_at=lot.completed_at,
                )
            )
        return rows

    async def get_late_lot_candidates(self, scope: KpiScope) -> list[LateLotCandidateRow]:
        q = select(ProductionLotOrmModel).where(
            ProductionLotOrmModel.status.in_(_OPEN_LOT_STATUSES)
        )
        if scope.project_id is not None:
            q = q.where(ProductionLotOrmModel.project_id == scope.project_id)
        if scope.customer_id is not None:
            q = q.join(ProjectOrmModel, ProductionLotOrmModel.project_id == ProjectOrmModel.id)
            q = q.where(ProjectOrmModel.customer_id == scope.customer_id)
        machine_scope = _machine_scope_exists(scope)
        if machine_scope is not None:
            q = q.where(machine_scope)
        lots = (await self._db.scalars(q)).all()
        if not lots:
            return []

        lot_ids = [lot.id for lot in lots]
        # Every non-canceled order of every candidate lot, so the "latest
        # order" pick below sees the lot's whole routing, not just orders
        # that happen to match the machine/pool scope above. Lateness is
        # a property of the LOT's overall finish, the scope only decides
        # which lots are even considered.
        order_rows = (
            await self._db.execute(
                select(ProductionOrderOrmModel, LotPositionOrmModel.lot_id)
                .join(
                    LotPositionOrmModel,
                    ProductionOrderOrmModel.lot_position_id == LotPositionOrmModel.id,
                )
                .where(
                    LotPositionOrmModel.lot_id.in_(lot_ids),
                    ProductionOrderOrmModel.status != ProductionOrderStatus.CANCELED.value,
                )
            )
        ).all()
        best_by_lot: dict[int, tuple[int, datetime]] = {}
        for order, lot_id in order_rows:
            effective_end = order.actual_end or order.planned_end
            if effective_end is None:
                continue
            current = best_by_lot.get(lot_id)
            if current is None or effective_end > current[1]:
                best_by_lot[lot_id] = (order.id, effective_end)

        return [
            LateLotCandidateRow(
                lot_id=lot.id,
                latest_order_id=best_by_lot[lot.id][0] if lot.id in best_by_lot else None,
                effective_end=best_by_lot[lot.id][1] if lot.id in best_by_lot else None,
            )
            for lot in lots
        ]

    async def get_waiting_time_rows(self, period: KpiPeriod, scope: KpiScope) -> list[WaitingRow]:
        candidate_rows = await self._query_waiting_candidates(period, scope)
        if not candidate_rows:
            return []

        (
            resolved,
            internal_predecessor_ids,
            external_predecessor_ids,
        ) = await self._resolve_waiting_predecessors(candidate_rows)
        internal_ready = await self._fetch_internal_ready_times(internal_predecessor_ids)
        external_ready = await self._fetch_external_ready_times(external_predecessor_ids)
        return self._build_waiting_rows(resolved, internal_ready, external_ready, period.zone)

    async def _query_waiting_candidates(
        self, period: KpiPeriod, scope: KpiScope
    ) -> "Sequence[Row[tuple[ProductionOrderOrmModel, int, str, int]]]":
        """Every sequence>1 order that actually started in the period,
        joined out to its own position's lot/kind/sequence for the
        predecessor lookup _resolve_waiting_predecessors does next."""
        q = (
            select(
                ProductionOrderOrmModel,
                LotPositionOrmModel.lot_id,
                LotPositionOrmModel.kind,
                LotPositionOrmModel.sequence,
            )
            .join(
                LotPositionOrmModel,
                ProductionOrderOrmModel.lot_position_id == LotPositionOrmModel.id,
            )
            .join(ProductionLotOrmModel, LotPositionOrmModel.lot_id == ProductionLotOrmModel.id)
            .where(
                ProductionOrderOrmModel.actual_start.isnot(None),
                ProductionOrderOrmModel.actual_start
                >= day_start_utc(period.date_from, period.zone),
                ProductionOrderOrmModel.actual_start < day_after_utc(period.date_to, period.zone),
                LotPositionOrmModel.sequence > 1,
            )
        )
        q = _apply_order_lot_scope(q, scope)
        return (await self._db.execute(q)).all()

    async def _resolve_waiting_predecessors(
        self, candidate_rows: "Sequence[Row[tuple[ProductionOrderOrmModel, int, str, int]]]"
    ) -> tuple[list[tuple[int, str, datetime, LotPositionOrmModel]], set[int], set[int]]:
        """Resolves each candidate order's own predecessor position (same
        lot, sequence - 1), batched via one query for every distinct lot in
        the page, and splits the resolved predecessors by kind so the
        caller can batch-fetch each kind's own readiness signal
        separately."""
        lot_ids = {lot_id for _order, lot_id, _kind, _sequence in candidate_rows}
        positions = (
            await self._db.scalars(
                select(LotPositionOrmModel).where(LotPositionOrmModel.lot_id.in_(lot_ids))
            )
        ).all()
        position_by_lot_and_sequence = {(p.lot_id, p.sequence): p for p in positions}

        resolved: list[tuple[int, str, datetime, LotPositionOrmModel]] = []
        internal_predecessor_ids: set[int] = set()
        external_predecessor_ids: set[int] = set()
        for order, lot_id, kind, sequence in candidate_rows:
            if order.actual_start is None:
                continue
            predecessor = position_by_lot_and_sequence.get((lot_id, sequence - 1))
            if predecessor is None:
                continue
            resolved.append((order.id, kind, order.actual_start, predecessor))
            if predecessor.kind in (LotPositionKind.INTERNAL.value, LotPositionKind.MIXED.value):
                internal_predecessor_ids.add(predecessor.id)
            if predecessor.kind in (LotPositionKind.EXTERNAL.value, LotPositionKind.MIXED.value):
                external_predecessor_ids.add(predecessor.id)
        return resolved, internal_predecessor_ids, external_predecessor_ids

    async def _fetch_internal_ready_times(self, position_ids: set[int]) -> dict[int, datetime]:
        """Each INTERNAL/MIXED predecessor's own latest actual_end across
        its production orders: the moment that position is genuinely
        done."""
        if not position_ids:
            return {}
        rows = (
            await self._db.execute(
                select(
                    ProductionOrderOrmModel.lot_position_id,
                    func.max(ProductionOrderOrmModel.actual_end),
                )
                .where(
                    ProductionOrderOrmModel.lot_position_id.in_(position_ids),
                    ProductionOrderOrmModel.actual_end.isnot(None),
                )
                .group_by(ProductionOrderOrmModel.lot_position_id)
            )
        ).all()
        return {
            position_id: latest_end for position_id, latest_end in rows if latest_end is not None
        }

    async def _fetch_external_ready_times(self, position_ids: set[int]) -> dict[int, datetime]:
        """Each EXTERNAL/MIXED predecessor's own order item delivery
        date, from its live line; a canceled line beside it no longer
        supplies the position."""
        if not position_ids:
            return {}
        rows = (
            await self._db.execute(
                select(OrderItemOrmModel.lot_position_id, OrderItemOrmModel.delivery_date).where(
                    OrderItemOrmModel.lot_position_id.in_(position_ids),
                    OrderItemOrmModel.delivery_date.isnot(None),
                    OrderItemOrmModel.canceled_at.is_(None),
                )
            )
        ).all()
        return {
            position_id: delivery_date
            for position_id, delivery_date in rows
            if delivery_date is not None
        }

    def _build_waiting_rows(
        self,
        resolved: list[tuple[int, str, datetime, LotPositionOrmModel]],
        internal_ready: dict[int, datetime],
        external_ready: dict[int, datetime],
        zone: tzinfo,
    ) -> list[WaitingRow]:
        result = []
        for order_id, kind, actual_start, predecessor in resolved:
            candidate_dates = []
            if predecessor.id in internal_ready:
                candidate_dates.append(internal_ready[predecessor.id].astimezone(zone).date())
            if predecessor.id in external_ready:
                candidate_dates.append(external_ready[predecessor.id].astimezone(zone).date())
            result.append(
                WaitingRow(
                    order_id=order_id,
                    position_kind=kind,
                    actual_start=actual_start,
                    predecessor_ready=max(candidate_dates) if candidate_dates else None,
                )
            )
        return result

    async def get_scrap_events(self, period: KpiPeriod, scope: KpiScope) -> list[ScrapReasonRow]:
        completion_q = (
            select(ProductionOrderCompletionOrmModel)
            .join(
                ProductionOrderOrmModel,
                ProductionOrderCompletionOrmModel.production_order_id == ProductionOrderOrmModel.id,
            )
            .join(
                LotPositionOrmModel,
                ProductionOrderOrmModel.lot_position_id == LotPositionOrmModel.id,
            )
            .join(ProductionLotOrmModel, LotPositionOrmModel.lot_id == ProductionLotOrmModel.id)
            .where(
                ProductionOrderCompletionOrmModel.quantity_scrap > 0,
                ProductionOrderCompletionOrmModel.scrap_reason.isnot(None),
                ProductionOrderCompletionOrmModel.completion_date >= period.date_from,
                ProductionOrderCompletionOrmModel.completion_date <= period.date_to,
            )
        )
        completion_q = _apply_order_lot_scope(completion_q, scope)

        events = [
            ScrapReasonRow(quantity=completion.quantity_scrap, reason=completion.scrap_reason)
            for completion in (await self._db.scalars(completion_q)).all()
            if completion.scrap_reason is not None
        ]

        delivery_q = (
            select(OrderItemDeliveryOrmModel)
            .join(
                OrderItemOrmModel, OrderItemDeliveryOrmModel.order_item_id == OrderItemOrmModel.id
            )
            .where(
                OrderItemDeliveryOrmModel.rejection_outcome == RejectionOutcome.LOST.value,
                OrderItemDeliveryOrmModel.quantity_rejected > 0,
                OrderItemDeliveryOrmModel.rejection_reason.isnot(None),
                OrderItemDeliveryOrmModel.delivery_date
                >= day_start_utc(period.date_from, period.zone),
                OrderItemDeliveryOrmModel.delivery_date
                < day_after_utc(period.date_to, period.zone),
            )
        )
        if scope.project_id is not None:
            delivery_q = delivery_q.where(OrderItemOrmModel.project_id == scope.project_id)
        if scope.customer_id is not None:
            delivery_q = delivery_q.join(
                ProjectOrmModel, OrderItemOrmModel.project_id == ProjectOrmModel.id
            )
            delivery_q = delivery_q.where(ProjectOrmModel.customer_id == scope.customer_id)

        events.extend(
            ScrapReasonRow(quantity=delivery.quantity_rejected, reason=delivery.rejection_reason)
            for delivery in (await self._db.scalars(delivery_q)).all()
            if delivery.rejection_reason is not None
        )
        return events

    async def get_supplier_deliveries(
        self, period: KpiPeriod, scope: KpiScope
    ) -> list[SupplierDeliveryRow]:
        q = (
            select(OrderItemDeliveryOrmModel, OrderItemOrmModel.supplier_id, SupplierOrmModel.name)
            .join(
                OrderItemOrmModel, OrderItemDeliveryOrmModel.order_item_id == OrderItemOrmModel.id
            )
            .join(SupplierOrmModel, OrderItemOrmModel.supplier_id == SupplierOrmModel.id)
            .where(
                OrderItemDeliveryOrmModel.delivery_date
                >= day_start_utc(period.date_from, period.zone),
                OrderItemDeliveryOrmModel.delivery_date
                < day_after_utc(period.date_to, period.zone),
            )
        )
        if scope.project_id is not None:
            q = q.where(OrderItemOrmModel.project_id == scope.project_id)
        if scope.customer_id is not None:
            q = q.join(ProjectOrmModel, OrderItemOrmModel.project_id == ProjectOrmModel.id)
            q = q.where(ProjectOrmModel.customer_id == scope.customer_id)
        rows = (await self._db.execute(q)).all()
        return [
            SupplierDeliveryRow(
                supplier_id=supplier_id,
                supplier_name=supplier_name,
                quantity=delivery.quantity,
                quantity_rejected=delivery.quantity_rejected,
                quantity_rejected_lost=(
                    delivery.quantity_rejected
                    if delivery.rejection_outcome == RejectionOutcome.LOST.value
                    else 0.0
                ),
            )
            for delivery, supplier_id, supplier_name in rows
        ]
