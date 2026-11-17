"""
SqlAlchemyBoughtItemUsages: the rows of other modules that name a bought
item, moved to another item when the item is merged away. Catalogue owns the
port (IBoughtItemUsages) and calls it in the lock order the lifecycle
writers use: lots, order lines, bought demands, raw material demands, then
the substitutions and the remaining references. The printer links are
Quality & documents' table, named here rather than imported, since Planning
& fulfillment sits below it.
"""

import sqlalchemy as sa
from sqlalchemy import Integer
from sqlalchemy import column
from sqlalchemy import select
from sqlalchemy import table
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_allocation_model import (
    BoughtItemAllocationOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_demand_item_model import (
    BoughtItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.quote_request_model import (
    QuoteOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.quote_request_model import (
    QuoteRequestLineOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_demand_item_model import (
    SourceItemDemandItemOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.product_device_model import (
    ProductDeviceComponentOrmModel,
)

_printer_bought_item_table = table(
    "printer_bought_item_table", column("printer_id", Integer), column("bought_item_id", Integer)
)


class SqlAlchemyBoughtItemUsages:
    """IBoughtItemUsages."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def merge_lot_sources(self, source_id: int, target_id: int) -> None:
        """Points the lots that draw the source item as their raw material at
        the target, locked first, as lots head the lock order, with FOR NO
        KEY UPDATE in ascending id order, their version moving."""
        ids = (
            await self._db.scalars(
                select(ProductionLotOrmModel.id)
                .where(ProductionLotOrmModel.source_bought_item_id == source_id)
                .order_by(ProductionLotOrmModel.id)
                .with_for_update(key_share=True)
            )
        ).all()
        if ids:
            await self._db.execute(
                sa.update(ProductionLotOrmModel)
                .where(ProductionLotOrmModel.id.in_(ids))
                .values(source_bought_item_id=target_id, version=ProductionLotOrmModel.version + 1)
                .execution_options(synchronize_session=False)
            )
        await self._db.flush()

    async def merge_order_items(self, source_id: int, target_id: int) -> None:
        """Points the source item's order lines at the target, locked and
        versioned like merge_demand_items. The caller merges the lines
        before the demands, as the lock order has it."""
        ids = (
            await self._db.scalars(
                select(OrderItemOrmModel.id)
                .where(OrderItemOrmModel.bought_item_id == source_id)
                .order_by(OrderItemOrmModel.id)
                .with_for_update(key_share=True)
            )
        ).all()
        if ids:
            await self._db.execute(
                sa.update(OrderItemOrmModel)
                .where(OrderItemOrmModel.id.in_(ids))
                .values(bought_item_id=target_id, version=OrderItemOrmModel.version + 1)
            )
        await self._db.flush()

    async def merge_demand_items(self, source_id: int, target_id: int) -> None:
        """Points the source item's demands at the target. The rows are
        locked in ascending id order first, as every lifecycle writer locks
        them, with FOR NO KEY UPDATE, and the version moves, so a writer
        holding an older copy of a demand is refused."""
        ids = (
            await self._db.scalars(
                select(BoughtItemDemandItemOrmModel.id)
                .where(BoughtItemDemandItemOrmModel.item_id == source_id)
                .order_by(BoughtItemDemandItemOrmModel.id)
                .with_for_update(key_share=True)
            )
        ).all()
        if ids:
            await self._db.execute(
                sa.update(BoughtItemDemandItemOrmModel)
                .where(BoughtItemDemandItemOrmModel.id.in_(ids))
                .values(item_id=target_id, version=BoughtItemDemandItemOrmModel.version + 1)
            )
        await self._db.flush()

    async def merge_source_demands(self, source_id: int, target_id: int) -> None:
        """Points the raw material demands for the source item at the target,
        after the bought demands, as source demands come last in the lock
        order."""
        ids = (
            await self._db.scalars(
                select(SourceItemDemandItemOrmModel.id)
                .where(SourceItemDemandItemOrmModel.bought_item_id == source_id)
                .order_by(SourceItemDemandItemOrmModel.id)
                .with_for_update(key_share=True)
            )
        ).all()
        if ids:
            await self._db.execute(
                sa.update(SourceItemDemandItemOrmModel)
                .where(SourceItemDemandItemOrmModel.id.in_(ids))
                .values(bought_item_id=target_id, version=SourceItemDemandItemOrmModel.version + 1)
                .execution_options(synchronize_session=False)
            )
        await self._db.flush()

    async def merge_substitutions(self, source_id: int, target_id: int) -> None:
        """Moves the allocations that name the source as their substitute to
        the target, after the lines and demands moved; one whose demand now
        names the target too is no substitution any more."""
        await self._db.execute(
            sa.update(BoughtItemAllocationOrmModel)
            .where(BoughtItemAllocationOrmModel.substitute_item_id == source_id)
            .values(substitute_item_id=target_id)
            .execution_options(synchronize_session=False)
        )
        same_item = (
            select(BoughtItemDemandItemOrmModel.id)
            .where(
                BoughtItemDemandItemOrmModel.id == BoughtItemAllocationOrmModel.demand_item_id,
                BoughtItemDemandItemOrmModel.item_id == target_id,
            )
            .exists()
        )
        await self._db.execute(
            sa.update(BoughtItemAllocationOrmModel)
            .where(BoughtItemAllocationOrmModel.substitute_item_id == target_id, same_item)
            .values(substitute_item_id=None, substitute_reason=None)
            .execution_options(synchronize_session=False)
        )
        await self._db.flush()

    async def merge_references(self, source_id: int, target_id: int) -> None:
        """Points the device components, quote request lines, quoted
        alternatives and printer links that name the source item at the
        target; a printer already linked to the target keeps one link."""
        for model in (ProductDeviceComponentOrmModel, QuoteRequestLineOrmModel):
            await self._db.execute(
                sa.update(model)
                .where(model.bought_item_id == source_id)
                .values(bought_item_id=target_id)
                .execution_options(synchronize_session=False)
            )
        await self._db.execute(
            sa.update(QuoteOrmModel)
            .where(QuoteOrmModel.substitute_bought_item_id == source_id)
            .values(substitute_bought_item_id=target_id)
            .execution_options(synchronize_session=False)
        )
        links = _printer_bought_item_table.c
        linked_to_target = select(links.printer_id).where(links.bought_item_id == target_id)
        await self._db.execute(
            sa.delete(_printer_bought_item_table).where(
                links.bought_item_id == source_id, links.printer_id.in_(linked_to_target)
            )
        )
        await self._db.execute(
            sa.update(_printer_bought_item_table)
            .where(links.bought_item_id == source_id)
            .values(bought_item_id=target_id)
        )
        await self._db.flush()
