"""
The rows a race test starts from, seeded through the real repositories on
the session the test passes and committed. The repository read graph of the
integration suite builds the referenced rows (users, items, project,
machine, supplier), so every foreign key Postgres enforces is satisfied.
The lot reworks its own made item, which exempts its first position from
waiting for raw material, so its production orders can start and complete
without a material delivery.
"""

import dataclasses
import itertools
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.models.admin_settings_model.orders import (
    AdminOrderSettingsOrmModel,
)
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_repository.demand_item import (
    SqlAlchemyBoughtItemDemandItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.order import (
    SqlAlchemyOrderRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.order_item import (
    SqlAlchemyOrderItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository.lot import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_machine_repository import (
    SqlAlchemyProductionMachineRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    SqlAlchemyProductionOrderRepository,
)
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.general import (
    AdminGeneralSettingsOrmModel,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration.repository_reads._graph import NOW
from tests.integration.repository_reads._graph import TODAY
from tests.integration.repository_reads._graph import Graph
from tests.integration.repository_reads._graph import make

_numbers = itertools.count(100)

EVERY_PERMISSION = sorted(
    value for name, value in vars(Permission).items() if name.isupper() and isinstance(value, str)
)


@dataclass
class Floor:
    db: AsyncSession
    graph: Graph
    actor: User

    async def lot(self) -> ProductionLot:
        """The graph's lot, reworking its own made item."""
        lot = await self.graph.lot()
        if lot.source_made_item_id is None:
            lot.source_item_id = None
            lot.source_made_item_id = lot.made_item_id
            lot = await SqlAlchemyProductionLotRepository(self.db).save(lot)
            await self.db.commit()
            self.graph._cache["lot"] = lot
        return lot

    async def running_order(self) -> ProductionOrder:
        """An order of 10 in progress on the lot's one internal position."""
        await self.lot()
        return await self.graph.production_order()

    async def machine(self) -> ProductionMachine:
        return await self.graph.machine()

    async def second_machine(self) -> ProductionMachine:
        """A second machine that can run the position's step."""
        method = await self.graph.fabrication_method()
        saved = await SqlAlchemyProductionMachineRepository(self.db).save(
            make(
                ProductionMachine,
                internal_name=f"MILL-{next(_numbers)}",
                fabrication_method_ids=[method.id],
                creator_id=self.graph.uid,
            )
        )
        await self.db.commit()
        return saved

    async def queued_order(
        self, quantity: float, *, machine_id: int, queue_sequence: int
    ) -> ProductionOrder:
        """A queued order on the lot's internal position, on `machine_id`."""
        await self.lot()
        position = await self.graph.internal_position()
        saved = await SqlAlchemyProductionOrderRepository(self.db).save(
            make(
                ProductionOrder,
                production_order_number=f"PO-{next(_numbers)}",
                status=ProductionOrderStatus.QUEUED,
                priority=UrgencyClass.NORMAL,
                pinned=False,
                queue_sequence=queue_sequence,
                quantity=quantity,
                quantity_completed=0.0,
                estimated_duration_minutes=30,
                creator_id=self.graph.uid,
                machine_id=machine_id,
                lot_position_id=position.id,
            )
        )
        await self.db.commit()
        return saved

    async def bought_line(self, quantity: float) -> OrderItem:
        """An ordered bought line of `quantity` on the graph's one supplier
        order, nothing delivered yet."""
        item = await self.graph.bought_item()
        order = await self.graph.order()
        project = await self.graph.project()
        saved = await SqlAlchemyOrderItemRepository(self.db).save(
            make(
                OrderItem,
                status=OrderItemStatus.ORDERED,
                quantity=quantity,
                quantity_delivered=0.0,
                unit="pcs",
                ordered_date=NOW,
                expected_delivery_date=TODAY,
                creator_id=self.graph.uid,
                orderer_id=self.graph.uid,
                receiver_id=self.graph.other_user.id,
                order_id=order.id,
                supplier_id=order.supplier_id,
                project_id=project.id,
                position=next(_numbers),
                line_type=OrderLineType.BOUGHT,
                bought_item_id=item.id,
            )
        )
        await self.db.commit()
        return saved

    async def second_order(self) -> Order:
        """Another ordered supplier order of the graph's supplier, empty."""
        first = await self.graph.order()
        saved = await SqlAlchemyOrderRepository(self.db).save(
            make(
                Order,
                order_number=f"O-{next(_numbers)}",
                status=OrderStatus.ORDERED,
                ordered_date=NOW,
                expected_delivery_date=TODAY,
                creator_id=self.graph.uid,
                supplier_id=first.supplier_id,
            )
        )
        await self.db.commit()
        return saved

    async def bought_demand(self, quantity: float) -> BoughtItemDemandItem:
        """An open demand for the graph's bought item."""
        item = await self.graph.bought_item()
        bucket = await self.graph.bought_bucket()
        fields: dict[str, Any] = {
            **await self.graph._demand_fields(),
            "status": BoughtItemDemandStatus.OPEN,
            "quantity": quantity,
        }
        saved = await SqlAlchemyBoughtItemDemandItemRepository(self.db).save(
            make(BoughtItemDemandItem, item_id=item.id, bucket_id=bucket.id, **fields)
        )
        await self.db.commit()
        return saved


async def seed(db: AsyncSession) -> Floor:
    """The settings the use cases read and the graph's two users; the actor
    holds every permission."""
    await SqlAlchemyAdminSettingsRepository(db).save_production(
        AdminProductionSettings(
            id=1,
            production_order_number_format="PON-{seq:05d}",
            default_weekly_hours={0: 480, 1: 480, 2: 480, 3: 480, 4: 480, 5: 0, 6: 0},
            default_external_lead_days=0,
            response_time_days=0,
            require_qa=False,
        )
    )
    # A delivery reads the delivery tolerances from the order settings.
    if await db.get(AdminOrderSettingsOrmModel, 1) is None:
        db.add(AdminOrderSettingsOrmModel(id=1))
    if await db.get(AdminGeneralSettingsOrmModel, 1) is None:
        db.add(
            AdminGeneralSettingsOrmModel(
                id=1,
                product_number_pattern="",
                project_number_pattern="",
                allow_headless_projects=True,
                empty_value_placeholder="-",
            )
        )
    await db.commit()
    graph = await Graph.seed(db)
    actor = dataclasses.replace(graph.user, permissions=EVERY_PERMISSION)
    return Floor(db=db, graph=graph, actor=actor)
