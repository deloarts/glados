"""
Gives demands seeded straight into the database the intents their stored
status stands for, and then lets the lifecycle reconciler store what their
facts derive, so the drift check after the test agrees with the seed. A
canceled demand gets its canceled_at and a fulfilled one its
fulfilled_manually_at; intents a seed set already are kept. Every other
status follows from the demand's allocations and the lines, lots and stock
they point at. The derived status must be the seeded one, so a seed cannot
drift into another status unnoticed. A caller that added allocations to a
demand stored before them names the status they derive with `expected`, and
a caller whose seed stores a status its facts do not give on purpose passes
`exact=False`. Flushes, the caller commits.
"""

from datetime import UTC
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.lifecycle_store import (
    sql_lifecycle_repositories,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_demand_item_model import (
    BoughtItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.made_item_demand_item_model import (
    MadeItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_demand_item_model import (
    SourceItemDemandItemOrmModel,
)
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from tests.integration._lot_facts import _SEEDER
from tests.integration._lot_facts import _Bus

_MODELS: dict[LifecycleAggregate, type] = {
    LifecycleAggregate.BOUGHT_DEMANDS: BoughtItemDemandItemOrmModel,
    LifecycleAggregate.MADE_DEMANDS: MadeItemDemandItemOrmModel,
    LifecycleAggregate.SOURCE_DEMANDS: SourceItemDemandItemOrmModel,
}


async def give_demand_facts(
    db: AsyncSession,
    family: LifecycleAggregate,
    *ids: int,
    exact: bool = True,
    expected: str | None = None,
) -> None:
    """Records the intents of each demand's stored status and reconciles
    the demands of one family, see the module docstring."""
    now = datetime.now(UTC)
    seeded: dict[int, str] = {}
    for demand_id in ids:
        demand = await db.get(_MODELS[family], demand_id, populate_existing=True)
        assert demand is not None, demand_id
        seeded[demand_id] = expected if expected is not None else demand.status
        if demand.status == "canceled" and demand.canceled_at is None:
            demand.canceled_at = now
        elif demand.status == "fulfilled" and demand.fulfilled_manually_at is None:
            demand.fulfilled_manually_at = now
    await db.flush()
    reconciler = LifecycleReconciler(sql_lifecycle_repositories(db), _Bus())
    reconciler.touch_demands(family, ids)
    await reconciler.run(_SEEDER, now, reason="seeded")
    await db.flush()
    if exact:
        for demand_id, status in seeded.items():
            demand = await db.get(_MODELS[family], demand_id, populate_existing=True)
            assert demand is not None
            assert demand.status == status, (
                f"{family.value} #{demand_id} was seeded {status} but its facts derive "
                f"{demand.status}."
            )
