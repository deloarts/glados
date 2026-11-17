"""
SqlAlchemyMadeItemUsages: the lots and demands that name a made item, moved
to another item when the item is merged away. Catalogue owns the port
(IMadeItemUsages).
"""

import sqlalchemy as sa
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.models.made_item_demand_item_model import (
    MadeItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)


class SqlAlchemyMadeItemUsages:
    """IMadeItemUsages."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def merge_lots_and_demands(self, source_id: int, target_id: int) -> None:
        """Points the lots and the demands that name the source item at the
        target. The lots are locked before the demands, each in ascending id
        order, as every lifecycle writer locks them, with FOR NO KEY UPDATE,
        and their version moves, so a writer holding an older copy is
        refused."""
        lot_ids = (
            await self._db.scalars(
                select(ProductionLotOrmModel.id)
                .where(
                    or_(
                        ProductionLotOrmModel.made_item_id == source_id,
                        ProductionLotOrmModel.source_made_item_id == source_id,
                    )
                )
                .order_by(ProductionLotOrmModel.id)
                .with_for_update(key_share=True)
            )
        ).all()
        for column in (
            ProductionLotOrmModel.made_item_id,
            ProductionLotOrmModel.source_made_item_id,
        ):
            await self._db.execute(
                sa.update(ProductionLotOrmModel)
                .where(ProductionLotOrmModel.id.in_(lot_ids), column == source_id)
                .values({column.key: target_id, "version": ProductionLotOrmModel.version + 1})
                .execution_options(synchronize_session=False)
            )
        demand_ids = (
            await self._db.scalars(
                select(MadeItemDemandItemOrmModel.id)
                .where(
                    or_(
                        MadeItemDemandItemOrmModel.made_item_id == source_id,
                        MadeItemDemandItemOrmModel.alteration_of_made_item_id == source_id,
                    )
                )
                .order_by(MadeItemDemandItemOrmModel.id)
                .with_for_update(key_share=True)
            )
        ).all()
        for column in (
            MadeItemDemandItemOrmModel.made_item_id,
            MadeItemDemandItemOrmModel.alteration_of_made_item_id,
        ):
            await self._db.execute(
                sa.update(MadeItemDemandItemOrmModel)
                .where(MadeItemDemandItemOrmModel.id.in_(demand_ids), column == source_id)
                .values({column.key: target_id, "version": MadeItemDemandItemOrmModel.version + 1})
                .execution_options(synchronize_session=False)
            )
        await self._db.flush()
