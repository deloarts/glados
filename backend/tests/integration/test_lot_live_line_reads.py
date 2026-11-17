"""
The lot reads that treat a canceled order line as gone and a scrapped lot as
terminal, on the throwaway SQLite file: the source panel and the source
approval reset skip a SCRAPPED lot, a position's line is its live one even
beside a canceled one, the orders panel offers a position whose only line
was canceled, and the waiting-time KPI reads a position's ready time from
its live line. The partial unique index takes a canceled and a live line
on one position.
"""

from datetime import UTC
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model import (
    LotPositionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.order_item import (
    SqlAlchemyOrderItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository.lot import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    SqlAlchemyProductionOrderInterruptionRepository,
)
from src.modules.fulfillment.domain.value_objects.source_approval_status import SourceApprovalStatus
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    LotFilterDto,
)
from src.modules.quality.adapters.outbound.persistence.repositories.production_kpi_repository import (
    SqlAlchemyProductionKpiRepository,
)
from tests.integration import _lifecycle_seed as seed
from tests.integration._lot_facts import give_lot_facts

CANCELED = datetime(2026, 1, 2, tzinfo=UTC)


async def _lot_ids(db: AsyncSession, **filters: object) -> set[int]:
    _, lots = await SqlAlchemyProductionLotRepository(db).get_multi(LotFilterDto(**filters))
    return {lot.id for lot in lots}


async def _scrapped_and_live(db: AsyncSession) -> tuple[ProductionLotOrmModel, ...]:
    """A scrapped and a live lot of a source item, both without their raw
    material demand and waiting for no approval."""
    lots = []
    for status in ("scrapped", "draft"):
        lot = await seed.lot(
            db,
            status,
            source_item_id=1,
            source_approval_status=SourceApprovalStatus.NOT_REQUIRED.value,
        )
        lots.append(lot)
    await give_lot_facts(db, *(lot.id for lot in lots))
    await db.commit()
    return tuple(lots)


async def _canceled_line(db: AsyncSession, at: LotPositionOrmModel) -> None:
    order = await seed.order(db, "canceled", canceled_at=CANCELED)
    await seed.line(db, order, "canceled", at=at, canceled_at=CANCELED)


async def test_the_source_panel_skips_a_scrapped_lot(db: AsyncSession) -> None:
    scrapped, live = await _scrapped_and_live(db)
    assert scrapped.status == "scrapped"

    assert await _lot_ids(db, actionable_for="source") == {live.id}


async def test_the_source_approval_reset_leaves_a_scrapped_lot_alone(db: AsyncSession) -> None:
    scrapped, live = await _scrapped_and_live(db)

    changed = await SqlAlchemyProductionLotRepository(db).reset_source_approval_for_setting_change(
        True
    )
    await db.commit()

    assert changed == 1
    await db.refresh(scrapped)
    await db.refresh(live)
    assert (scrapped.source_approval_status, live.source_approval_status) == (
        SourceApprovalStatus.NOT_REQUIRED.value,
        SourceApprovalStatus.PENDING.value,
    )


async def test_a_positions_line_is_the_live_one_beside_a_canceled_one(db: AsyncSession) -> None:
    lot = await seed.lot(db, "draft")
    position = await seed.position(db, lot, "unassigned", "pending")
    order = await seed.order(db, "draft")
    live = await seed.line(db, order, "pending", at=position)
    await _canceled_line(db, position)
    await give_lot_facts(db, lot.id)
    await db.commit()

    found = await SqlAlchemyOrderItemRepository(db).get_by_lot_position_id(position.id)

    assert found is not None
    assert found.id == live.id
    await db.refresh(position)
    assert position.kind == "external"


async def test_the_orders_panel_offers_a_position_whose_line_was_canceled(
    db: AsyncSession,
) -> None:
    freed = await seed.lot(db, "draft")
    freed_position = await seed.position(db, freed, "unassigned", "pending")
    await _canceled_line(db, freed_position)
    supplied = await seed.lot(db, "draft")
    supplied_position = await seed.position(db, supplied, "unassigned", "pending")
    await seed.line(db, await seed.order(db, "draft"), "pending", at=supplied_position)
    await give_lot_facts(db, freed.id, supplied.id)
    await db.commit()

    assert await _lot_ids(db, actionable_for="orders") == {freed.id}


async def test_the_waiting_kpi_reads_the_ready_time_of_the_live_line(db: AsyncSession) -> None:
    lot = await seed.lot(db, "in_progress")
    position = await seed.position(db, lot, "unassigned", "pending")
    live_order = await seed.order(db, "partially_delivered", ordered_date=CANCELED)
    arrived = datetime(2026, 1, 5, tzinfo=UTC)
    await seed.line(
        db,
        live_order,
        "partially_delivered",
        at=position,
        ordered_date=CANCELED,
        quantity_delivered=4.0,
        delivery_date=arrived,
    )
    # Canceled after the live line was placed, so it comes last.
    order = await seed.order(db, "canceled", canceled_at=CANCELED)
    await seed.line(
        db, order, "canceled", at=position, canceled_at=CANCELED, delivery_date=CANCELED
    )
    await give_lot_facts(db, lot.id)
    await db.commit()
    kpis = SqlAlchemyProductionKpiRepository(
        db, SqlAlchemyProductionOrderInterruptionRepository(db)
    )

    ready = await kpis._fetch_external_ready_times({position.id})

    assert {key: value.replace(tzinfo=UTC) for key, value in ready.items()} == {
        position.id: arrived
    }
