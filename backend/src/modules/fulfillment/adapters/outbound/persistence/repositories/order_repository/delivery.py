"""
Concrete SQLAlchemy implementation for the OrderItemDelivery aggregate.
"""

from sqlalchemy import case
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_delivery_model import (
    OrderItemDeliveryOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository._mappers import (
    delivery_load_options,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository._mappers import (
    delivery_orm_to_entity,
)
from src.modules.fulfillment.domain.entities.order_item_delivery import OrderItemDelivery
from src.modules.fulfillment.domain.services.lifecycle.delivery_totals import DeliveryTotals
from src.modules.fulfillment.domain.value_objects.rejection_outcome import RejectionOutcome
from src.modules.platform.adapters.outbound.persistence.statements import by_id

# ══════════════════════════════════════════════════════════════════════
# OrderItemDelivery repository
# ══════════════════════════════════════════════════════════════════════


class SqlAlchemyOrderItemDeliveryRepository:
    """
    Append-only audit trail of delivery events. Rows are never updated
    or deleted, correcting a delivery means recording a new event.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _reload(self, id: int) -> OrderItemDeliveryOrmModel:
        """Re-selects a just-written row with everything the mapper reads.
        populate_existing re-reads every column, so server defaults arrive as
        with refresh(), and applies the loader options to the object already
        in the identity map."""
        return (
            await self._db.scalars(
                by_id(OrderItemDeliveryOrmModel, id, *delivery_load_options(), refresh=True)
            )
        ).one()

    async def get_by_id(self, id: int) -> OrderItemDelivery | None:
        orm = await self._db.scalar(by_id(OrderItemDeliveryOrmModel, id, *delivery_load_options()))
        return delivery_orm_to_entity(orm) if orm else None

    async def get_by_order_item_id(self, order_item_id: int) -> list[OrderItemDelivery]:
        rows = (
            await self._db.scalars(
                select(OrderItemDeliveryOrmModel)
                .options(*delivery_load_options())
                .where(OrderItemDeliveryOrmModel.order_item_id == order_item_id)
                .order_by(OrderItemDeliveryOrmModel.id)
            )
        ).all()
        return [delivery_orm_to_entity(r) for r in rows]

    async def get_by_order_item_ids(self, order_item_ids: list[int]) -> list[OrderItemDelivery]:
        if not order_item_ids:
            return []
        rows = (
            await self._db.scalars(
                select(OrderItemDeliveryOrmModel)
                .options(*delivery_load_options())
                .where(OrderItemDeliveryOrmModel.order_item_id.in_(order_item_ids))
                .order_by(OrderItemDeliveryOrmModel.id)
            )
        ).all()
        return [delivery_orm_to_entity(r) for r in rows]

    async def get_totals_by_order_item_ids(
        self, order_item_ids: list[int]
    ) -> dict[int, DeliveryTotals]:
        if not order_item_ids:
            return {}
        row = OrderItemDeliveryOrmModel
        lost = case(
            (row.rejection_outcome == RejectionOutcome.LOST.value, row.quantity_rejected),
            else_=0.0,
        )
        rows = await self._db.execute(
            select(
                row.order_item_id,
                func.coalesce(func.sum(row.quantity), 0.0),
                func.coalesce(func.sum(row.quantity_rejected), 0.0),
                func.coalesce(func.sum(lost), 0.0),
            )
            .where(row.order_item_id.in_(order_item_ids))
            .group_by(row.order_item_id)
        )
        return {
            order_item_id: DeliveryTotals(
                accepted=float(accepted), rejected=float(rejected), lost=float(lost_sum)
            )
            for order_item_id, accepted, rejected, lost_sum in rows.all()
        }

    async def save(self, delivery: OrderItemDelivery) -> OrderItemDelivery:
        orm = OrderItemDeliveryOrmModel(
            order_item_id=delivery.order_item_id,
            quantity=delivery.quantity,
            delivery_date=delivery.delivery_date,
            storage_place=delivery.storage_place,
            receiver_id=delivery.receiver_id,
            created=delivery.created,
            quantity_rejected=delivery.quantity_rejected,
            rejection_reason=delivery.rejection_reason,
            rejection_note=delivery.rejection_note,
            rejection_outcome=(
                delivery.rejection_outcome.value if delivery.rejection_outcome is not None else None
            ),
            corrects_delivery_id=delivery.corrects_delivery_id,
            correction_reason=delivery.correction_reason,
            supplier_batch=delivery.supplier_batch,
            delivery_note_number=delivery.delivery_note_number,
            certificate_reference=delivery.certificate_reference,
            damage_noted_on_delivery_note=delivery.damage_noted_on_delivery_note,
        )
        self._db.add(orm)
        await self._db.flush()
        return delivery_orm_to_entity(await self._reload(orm.id))
