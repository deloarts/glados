"""
The SQL repositories the lifecycle reconciler and drift report read and
write, bundled on one session for callers outside the request scope: the
admin CLI and the integration suite's drift check. Requests get theirs from
get_lifecycle_reconciler in deps/lifecycle.py.

start_read_only_snapshot makes the session's transaction REPEATABLE READ and
READ ONLY on Postgres, so a drift report reads every page from one snapshot
and cannot write. It must be the transaction's first statement. SQLite, the
test database, has neither setting.

The models name related models by string, and the first query configures
every mapper, so this module imports alembic_imports, which loads the whole
models package for the out-of-process CLI.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import src.modules.platform.adapters.outbound.persistence.alembic_imports  # noqa: F401
from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_repository.allocation import (
    SqlAlchemyBoughtItemAllocationRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_repository.demand_item import (
    SqlAlchemyBoughtItemDemandItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.made_item_demand_repository import (
    SqlAlchemyMadeItemAllocationRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.made_item_demand_repository import (
    SqlAlchemyMadeItemDemandItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository import (
    SqlAlchemyOrderItemDeliveryRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository import (
    SqlAlchemyOrderItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository import (
    SqlAlchemyOrderRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    SqlAlchemyProductionOrderRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.quote_request_repository import (
    SqlAlchemyQuoteRequestRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.source_item_allocation_repository import (
    SqlAlchemySourceItemAllocationRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.source_item_demand_repository import (
    SqlAlchemySourceItemDemandRepository,
)
from src.modules.fulfillment.application.services.lifecycle_loader import LifecycleRepositories

_READ_ONLY_SNAPSHOT = text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")


def sql_lifecycle_repositories(db: AsyncSession) -> LifecycleRepositories:
    return LifecycleRepositories(
        lots=SqlAlchemyProductionLotRepository(db),
        production_orders=SqlAlchemyProductionOrderRepository(db),
        orders=SqlAlchemyOrderRepository(db),
        order_items=SqlAlchemyOrderItemRepository(db),
        bought_demands=SqlAlchemyBoughtItemDemandItemRepository(db),
        bought_allocations=SqlAlchemyBoughtItemAllocationRepository(db),
        made_demands=SqlAlchemyMadeItemDemandItemRepository(db),
        made_allocations=SqlAlchemyMadeItemAllocationRepository(db),
        source_demands=SqlAlchemySourceItemDemandRepository(db),
        source_allocations=SqlAlchemySourceItemAllocationRepository(db),
        quote_requests=SqlAlchemyQuoteRequestRepository(db),
        deliveries=SqlAlchemyOrderItemDeliveryRepository(db),
    )


async def start_read_only_snapshot(db: AsyncSession) -> None:
    """See the module docstring; a no-op on SQLite."""
    if db.get_bind().dialect.name == "postgresql":
        await db.execute(_READ_ONLY_SNAPSHOT)
