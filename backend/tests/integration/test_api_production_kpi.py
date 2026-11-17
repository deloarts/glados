"""
HTTP-level round trip for every /api/v1/web/production-kpi endpoint. The
whole dataset (project, made items, lots, positions, fabrication
methods/steps, machines, orders, an interruption, completions, and one
machine downtime) is seeded directly through the real repositories, the
same pattern test_api_production_order_time_tracking.py and
test_api_machine_downtimes.py use; only the GET requests under test go
through HTTP. Every number in the assertions is derived by hand in the
comments below from the seeded rows, using the exact same arithmetic
kpi_rules.py's formulas apply.

Dataset (period under test: 2026-03-02 Monday through 2026-03-06 Friday,
one ISO week, 2026-W10; the default weekly calendar is Mon-Fri 480
minutes, weekend 0, so each machine has 2400 available minutes over the
period):

Machines: M1, M2 (default calendar, no working-hours override). M1 has
one closed downtime 2026-03-03 08:00-10:00 UTC (120 minutes) inside the
period.

Lot A (COMPLETED, required_delivery_date 2026-03-04, completed_at
2026-03-03T00:00Z, created 2026-02-25T00:00Z -> throughput 6.0 days,
on time since 2026-03-03 <= 2026-03-04): two INTERNAL positions of 10,
closed short to 9 by the piece A2 rejected at the last position, so
position 2 and the lot hold 9 and every stored completed count equals
what the completion rows derive.
  Position 1 (sequence 1, fabrication method "Milling"):
    Order A1 on M1, estimated 120 min, actual 08:00-10:00 (120 min
    elapsed), one closed interruption 08:30-08:45 (15 min) -> net 105
    min. planned_end_at_start 12:00 -> actual_end <= baseline: ON TIME.
    Estimate-accuracy ratio: 105/120 = 0.875. Completion: quantity 10,
    accepted 10, rejected 0.
  Position 2 (sequence 2, fabrication method "Deburring"):
    Order A2 on M1, estimated 50 min, actual 2026-03-03 08:00-09:00 (60
    min, no interruption) -> net 60 min. planned_end_at_start 10:00 ->
    ON TIME. Estimate-accuracy ratio: 60/50 = 1.2. Completion: quantity
    10, accepted 9, rejected 1, rework 1, scrap 0. Waiting time:
    predecessor (position 1) is INTERNAL, its only order (A1) has
    actual_end 2026-03-02 (date);
    A2's actual_start date is 2026-03-03 -> 1 day wait, position kind
    INTERNAL (A2's own position).

Lot B (COMPLETED, required_delivery_date 2026-03-03, completed_at
2026-03-05T00:00Z, created 2026-02-26T00:00Z -> throughput 7.0 days,
LATE since 2026-03-05 > 2026-03-03): one INTERNAL position (sequence 1,
fabrication method "Turning"), quantity 8 across two orders, closed
short to 6 by the two pieces B2 rejected:
  Order B1 on M2, estimated 40 min, actual 2026-03-03 08:00-09:00 (60
    min, no interruption) -> net 60 min. planned_end_at_start 08:30 ->
    actual_end > baseline: LATE. Estimate-accuracy ratio: 60/40 = 1.5.
    Completion: quantity 5, accepted 5, rejected 0.
  Order B2 on M1, estimated 30 min, actual 2026-03-04 08:00-08:30 (30
    min, no interruption) -> net 30 min. planned_end_at_start 09:00 ->
    ON TIME. Estimate-accuracy ratio: 30/30 = 1.0. Completion: quantity
    3, accepted 1, rejected 2, rework 0, scrap 2.
  "Turning" estimate accuracy: ratios [1.5, 1.0] -> median 1.25, count 2.

Lot C (OPEN/PLANNED, required_delivery_date 2026-03-01, no completed_at):
one INTERNAL position (sequence 1), quantity 8:
  Order C1 on M1, QUEUED, no actual_start/actual_end, planned_end
    2026-03-10T12:00Z, estimated 90 min, never completed. Effective end
    (no actual_end yet) is planned_end -> projected 2026-03-10, 9 days
    past the 2026-03-01 target: LATE. The order has no raw-material
    demand linked (sequence 1, no input_demand_id, not an alteration),
    so is_unplannable_for_missing_material is true and
    explain_earliest_start resolves "missing_material" with no date.

Aggregates over the 4 completed orders (A1, A2, B1, B2), all with
actual_end inside the period:
  Schedule adherence: on time [A1, A2, B2], late [B1] -> 3/4 = 0.75.
  First pass yield: accepted sum 10+9+5+1=25, quantity sum
    10+10+5+3=28 -> 25/28.
  Scrap ratio: scrap sum 0+0+0+2=2 -> 2/28. Rework ratio: rework sum
    0+1+0+0=1 -> 1/28.
  Utilization: M1 net 105+60+30=195 / 2400 available = 0.08125; M2 net
    60 / 2400 = 0.025; manual bucket net 0, ratio None (no denominator).
  Availability: M1 (2400-120)/2400 = 0.95; M2 2400/2400 = 1.0.
  Overall (cross-machine) utilization for the OEE gate: (195+60) /
    (2400+2400) = 255/4800 = 0.053125. Overall availability:
    ((2400-120)+2400)/4800 = 4680/4800 = 0.975.
  Performance: estimated sum 120+50+40+30=240, net sum
    105+60+60+30=255 -> 240/255, not capped (< 1).
  OEE = availability(0.975) * performance(240/255) * yield(25/28)
    = 0.819327731092437 (all three gating ratios are computable).

Two completed lots (A, B): on-time delivery 1/2 = 0.5. Throughput days
[6.0, 7.0] -> median 6.5, p90 (linear interpolation, rank
(2-1)*0.9=0.9) 6.0 + (7.0-6.0)*0.9 = 6.9.

Weekly series: the whole period is one ISO week (2026-W10, Monday
2026-03-02), so its one point equals the unfiltered summary figures
above (schedule adherence 0.75, on-time delivery 0.5).

Quality by item: made item MI-A (from A1+A2) completed 20, rejected 1,
rework 1, scrap 0, yield 19/20 = 0.95; made item MI-B (from B1+B2)
completed 8, rejected 2, rework 0, scrap 2, yield 6/8 = 0.75.

A second assertion block re-reads /estimate-accuracy filtered to
machine_id=M1, where B1 (on M2) drops out of the "Turning" group,
leaving only B2's ratio (1.0, count 1).
"""

from datetime import UTC
from datetime import date
from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.fabrication_method_repository import (
    SqlAlchemyFabricationMethodRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.made_item_repository.item import (
    SqlAlchemyMadeItemRepository,
)
from src.modules.catalogue.domain.entities.fabrication_method import FabricationMethod
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.fulfillment.adapters.outbound.persistence.repositories.machine_downtime_repository import (
    SqlAlchemyMachineDowntimeRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository.lot import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_machine_repository import (
    SqlAlchemyProductionMachineRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    SqlAlchemyProductionOrderInterruptionRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    SqlAlchemyProductionOrderRepository,
)
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.machine_downtime import MachineDowntime
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)
from src.modules.fulfillment.domain.entities.production_order_interruption import (
    ProductionOrderInterruption,
)
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.machine_downtime_reason import (
    MachineDowntimeReason,
)
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project
from tests.integration.conftest import auth_headers

KPI_BASE = "/api/v1/web/production-kpi"
PERIOD = {"date_from": "2026-03-02", "date_to": "2026-03-06"}


@pytest.fixture(autouse=True)
async def _seed_production_settings(db: Session) -> None:
    await SqlAlchemyAdminSettingsRepository(db).save_production(
        AdminProductionSettings(
            id=1,
            production_order_number_format="PON-{yy}-{seq:05d}",
            default_weekly_hours={0: 480, 1: 480, 2: 480, 3: 480, 4: 480, 5: 0, 6: 0},
            default_external_lead_days=0,
            response_time_days=1,
            require_qa=False,
        )
    )
    await db.commit()


@pytest.fixture
async def viewer(create_user) -> User:
    return await create_user(username="kpi-viewer", email="kpi-viewer@example.com", permissions=[])


async def _made_item(db: Session, creator_id: int, article_name: str) -> MadeItem:
    seeded = await SqlAlchemyMadeItemRepository(db).save(
        MadeItem(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            revision="0",
            revision_date=None,
            revision_note=None,
            article_name=article_name,
            status=MadeItemCatalogueStatus.ACTIVE,
            data_source=DataSource.WEB,
            part_number=None,
            material=None,
            mass=None,
            base_size=None,
            note=None,
            weblink=None,
            files=[],
            creator_id=creator_id,
            approver_id=None,
            bought_item_id=None,
            source_item_id=None,
            article_group_ids=[],
            successor_item_id=None,
            changed_by_id=None,
        )
    )
    await db.commit()
    return seeded


async def _fabrication_method(db: Session, creator_id: int, name: str) -> FabricationMethod:
    return await SqlAlchemyFabricationMethodRepository(db).save(
        FabricationMethod(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            name=LocalizedText({"enGB": name}),
            label_color="#999999",
            label_font_color="#000000",
            description=LocalizedText(),
            creator_id=creator_id,
        )
    )


async def _machine(db: Session, creator_id: int, internal_name: str) -> ProductionMachine:
    saved = await SqlAlchemyProductionMachineRepository(db).save(
        ProductionMachine(
            id=0,
            created=datetime.now(UTC).date(),
            changed=None,
            changes=[],
            archived=False,
            internal_name=internal_name,
            vendor="Contoso",
            model="VF-2",
            fabrication_method_ids=[],
            max_part_dimension=None,
            note=None,
            creator_id=creator_id,
        )
    )
    await db.commit()
    return saved


def _order(
    *,
    creator_id: int,
    number: str,
    machine_id: int,
    position_id: int,
    quantity: float,
    quantity_completed: float,
    estimated_duration_minutes: int,
    status: ProductionOrderStatus,
    actual_start: datetime | None,
    actual_end: datetime | None,
    planned_end: datetime | None,
    planned_end_at_start: datetime | None,
) -> ProductionOrder:
    return ProductionOrder(
        id=0,
        created=datetime.now(UTC),
        changed=None,
        changes=[],
        production_order_number=number,
        status=status,
        priority=UrgencyClass.NORMAL,
        pinned=False,
        queue_sequence=1,
        quantity=quantity,
        quantity_completed=quantity_completed,
        estimated_duration_minutes=estimated_duration_minutes,
        note=None,
        planned_start=None,
        planned_end=planned_end,
        not_before=None,
        actual_start=actual_start,
        actual_end=actual_end,
        creator_id=creator_id,
        machine_id=machine_id,
        lot_position_id=position_id,
        planned_end_at_start=planned_end_at_start,
    )


def _completion(
    order_id: int,
    *,
    quantity: float,
    accepted: float,
    rejected: float,
    rework: float,
    scrap: float,
    when: date,
) -> ProductionOrderCompletion:
    return ProductionOrderCompletion(
        id=0,
        production_order_id=order_id,
        quantity=quantity,
        quantity_accepted=accepted,
        quantity_rejected=rejected,
        completion_date=when,
        note=None,
        operator_id=0,
        recorded_by_id=0,
        created=datetime.now(UTC),
        quantity_rework=rework,
        quantity_scrap=scrap,
    )


@pytest.fixture
async def seeded(db: Session, viewer: User) -> dict:
    creator_id = viewer.id
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=creator_id, project_number="PRJ-KPI")
    )
    milling = await _fabrication_method(db, creator_id, "Milling")
    deburring = await _fabrication_method(db, creator_id, "Deburring")
    turning = await _fabrication_method(db, creator_id, "Turning")
    m1 = await _machine(db, creator_id, "KPI-M1")
    m2 = await _machine(db, creator_id, "KPI-M2")

    lot_repo = SqlAlchemyProductionLotRepository(db)
    order_repo = SqlAlchemyProductionOrderRepository(db)
    interruption_repo = SqlAlchemyProductionOrderInterruptionRepository(db)

    # ── Lot A: two positions, both completed, on time ───────────────
    item_a = await _made_item(db, creator_id, "KPI item A")
    lot_a = await lot_repo.save(
        ProductionLot(
            id=0,
            created=datetime(2026, 2, 25, tzinfo=UTC),
            changed=None,
            changes=[],
            lot_number="LOT-KPI-A",
            quantity=9.0,
            status=LotStatus.COMPLETED,
            priority=UrgencyClass.NORMAL,
            note=None,
            creator_id=creator_id,
            made_item_id=item_a.id,
            project_id=project.id,
            input_demand_id=None,
            required_delivery_date=date(2026, 3, 4),
            completed_at=datetime(2026, 3, 3, tzinfo=UTC),
        )
    )
    pos_a1 = await lot_repo.save_position(
        LotPosition(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            sequence=1,
            kind=LotPositionKind.INTERNAL,
            status=LotPositionStatus.COMPLETED,
            quantity=10.0,
            quantity_completed=10.0,
            note=None,
            creator_id=creator_id,
            lot_id=lot_a.id,
        )
    )
    await lot_repo.save_step(
        LotStep(
            id=0,
            created=datetime.now(UTC),
            note=None,
            estimated_setup_minutes=None,
            estimated_minutes_per_piece=None,
            sequence=1,
            creator_id=creator_id,
            fabrication_method_id=milling.id,
            lot_id=lot_a.id,
            position_id=pos_a1.id,
            source_process_id=None,
        )
    )
    pos_a2 = await lot_repo.save_position(
        LotPosition(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            sequence=2,
            kind=LotPositionKind.INTERNAL,
            status=LotPositionStatus.COMPLETED,
            quantity=9.0,
            quantity_completed=9.0,
            note=None,
            creator_id=creator_id,
            lot_id=lot_a.id,
        )
    )
    await lot_repo.save_step(
        LotStep(
            id=0,
            created=datetime.now(UTC),
            note=None,
            estimated_setup_minutes=None,
            estimated_minutes_per_piece=None,
            sequence=2,
            creator_id=creator_id,
            fabrication_method_id=deburring.id,
            lot_id=lot_a.id,
            position_id=pos_a2.id,
            source_process_id=None,
        )
    )
    order_a1 = await order_repo.save(
        _order(
            creator_id=creator_id,
            number="PO-A1",
            machine_id=m1.id,
            position_id=pos_a1.id,
            quantity=10.0,
            quantity_completed=10.0,
            estimated_duration_minutes=120,
            status=ProductionOrderStatus.COMPLETED,
            actual_start=datetime(2026, 3, 2, 8, 0, tzinfo=UTC),
            actual_end=datetime(2026, 3, 2, 10, 0, tzinfo=UTC),
            planned_end=datetime(2026, 3, 2, 12, 0, tzinfo=UTC),
            planned_end_at_start=datetime(2026, 3, 2, 12, 0, tzinfo=UTC),
        )
    )
    await db.commit()
    await interruption_repo.add(
        ProductionOrderInterruption(
            id=0,
            production_order_id=order_a1.id,
            paused_at=datetime(2026, 3, 2, 8, 30, tzinfo=UTC),
            resumed_at=datetime(2026, 3, 2, 8, 45, tzinfo=UTC),
            paused_by_id=creator_id,
            resumed_by_id=creator_id,
            created=datetime(2026, 3, 2, 8, 30, tzinfo=UTC),
        )
    )
    await order_repo.save_completion(
        _completion(
            order_a1.id,
            quantity=10.0,
            accepted=10.0,
            rejected=0.0,
            rework=0.0,
            scrap=0.0,
            when=date(2026, 3, 2),
        )
    )
    await db.commit()
    order_a2 = await order_repo.save(
        _order(
            creator_id=creator_id,
            number="PO-A2",
            machine_id=m1.id,
            position_id=pos_a2.id,
            quantity=10.0,
            quantity_completed=9.0,
            estimated_duration_minutes=50,
            status=ProductionOrderStatus.COMPLETED,
            actual_start=datetime(2026, 3, 3, 8, 0, tzinfo=UTC),
            actual_end=datetime(2026, 3, 3, 9, 0, tzinfo=UTC),
            planned_end=datetime(2026, 3, 3, 10, 0, tzinfo=UTC),
            planned_end_at_start=datetime(2026, 3, 3, 10, 0, tzinfo=UTC),
        )
    )
    await db.commit()
    await order_repo.save_completion(
        _completion(
            order_a2.id,
            quantity=10.0,
            accepted=9.0,
            rejected=1.0,
            rework=1.0,
            scrap=0.0,
            when=date(2026, 3, 3),
        )
    )
    await db.commit()

    # ── Lot B: one position, two orders, one late ───────────────────
    item_b = await _made_item(db, creator_id, "KPI item B")
    lot_b = await lot_repo.save(
        ProductionLot(
            id=0,
            created=datetime(2026, 2, 26, tzinfo=UTC),
            changed=None,
            changes=[],
            lot_number="LOT-KPI-B",
            quantity=6.0,
            status=LotStatus.COMPLETED,
            priority=UrgencyClass.NORMAL,
            note=None,
            creator_id=creator_id,
            made_item_id=item_b.id,
            project_id=project.id,
            input_demand_id=None,
            required_delivery_date=date(2026, 3, 3),
            completed_at=datetime(2026, 3, 5, tzinfo=UTC),
        )
    )
    pos_b1 = await lot_repo.save_position(
        LotPosition(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            sequence=1,
            kind=LotPositionKind.INTERNAL,
            status=LotPositionStatus.COMPLETED,
            quantity=6.0,
            quantity_completed=6.0,
            note=None,
            creator_id=creator_id,
            lot_id=lot_b.id,
        )
    )
    await lot_repo.save_step(
        LotStep(
            id=0,
            created=datetime.now(UTC),
            note=None,
            estimated_setup_minutes=None,
            estimated_minutes_per_piece=None,
            sequence=1,
            creator_id=creator_id,
            fabrication_method_id=turning.id,
            lot_id=lot_b.id,
            position_id=pos_b1.id,
            source_process_id=None,
        )
    )
    order_b1 = await order_repo.save(
        _order(
            creator_id=creator_id,
            number="PO-B1",
            machine_id=m2.id,
            position_id=pos_b1.id,
            quantity=5.0,
            quantity_completed=5.0,
            estimated_duration_minutes=40,
            status=ProductionOrderStatus.COMPLETED,
            actual_start=datetime(2026, 3, 3, 8, 0, tzinfo=UTC),
            actual_end=datetime(2026, 3, 3, 9, 0, tzinfo=UTC),
            planned_end=datetime(2026, 3, 3, 8, 30, tzinfo=UTC),
            planned_end_at_start=datetime(2026, 3, 3, 8, 30, tzinfo=UTC),
        )
    )
    await db.commit()
    await order_repo.save_completion(
        _completion(
            order_b1.id,
            quantity=5.0,
            accepted=5.0,
            rejected=0.0,
            rework=0.0,
            scrap=0.0,
            when=date(2026, 3, 3),
        )
    )
    await db.commit()
    order_b2 = await order_repo.save(
        _order(
            creator_id=creator_id,
            number="PO-B2",
            machine_id=m1.id,
            position_id=pos_b1.id,
            quantity=3.0,
            quantity_completed=1.0,
            estimated_duration_minutes=30,
            status=ProductionOrderStatus.COMPLETED,
            actual_start=datetime(2026, 3, 4, 8, 0, tzinfo=UTC),
            actual_end=datetime(2026, 3, 4, 8, 30, tzinfo=UTC),
            planned_end=datetime(2026, 3, 4, 9, 0, tzinfo=UTC),
            planned_end_at_start=datetime(2026, 3, 4, 9, 0, tzinfo=UTC),
        )
    )
    await db.commit()
    await order_repo.save_completion(
        _completion(
            order_b2.id,
            quantity=3.0,
            accepted=1.0,
            rejected=2.0,
            rework=0.0,
            scrap=2.0,
            when=date(2026, 3, 4),
        )
    )
    await db.commit()

    # ── Lot C: open, one unstarted order, projected late ────────────
    item_c = await _made_item(db, creator_id, "KPI item C")
    lot_c = await lot_repo.save(
        ProductionLot(
            id=0,
            created=datetime(2026, 2, 20, tzinfo=UTC),
            changed=None,
            changes=[],
            lot_number="LOT-KPI-C",
            quantity=8.0,
            status=LotStatus.PLANNED,
            priority=UrgencyClass.NORMAL,
            note=None,
            creator_id=creator_id,
            made_item_id=item_c.id,
            project_id=project.id,
            input_demand_id=None,
            required_delivery_date=date(2026, 3, 1),
        )
    )
    pos_c1 = await lot_repo.save_position(
        LotPosition(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            sequence=1,
            kind=LotPositionKind.INTERNAL,
            status=LotPositionStatus.ORDERED_OR_QUEUED,
            quantity=8.0,
            quantity_completed=0.0,
            note=None,
            creator_id=creator_id,
            lot_id=lot_c.id,
        )
    )
    await order_repo.save(
        _order(
            creator_id=creator_id,
            number="PO-C1",
            machine_id=m1.id,
            position_id=pos_c1.id,
            quantity=8.0,
            quantity_completed=0.0,
            estimated_duration_minutes=90,
            status=ProductionOrderStatus.QUEUED,
            actual_start=None,
            actual_end=None,
            planned_end=datetime(2026, 3, 10, 12, 0, tzinfo=UTC),
            planned_end_at_start=None,
        )
    )
    await db.commit()

    # ── Machine downtime on M1 ───────────────────────────────────────
    downtime_repo = SqlAlchemyMachineDowntimeRepository(db)
    await downtime_repo.save(
        MachineDowntime(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            machine_id=m1.id,
            started_at=datetime(2026, 3, 3, 8, 0, tzinfo=UTC),
            ended_at=datetime(2026, 3, 3, 10, 0, tzinfo=UTC),
            reason=MachineDowntimeReason.BREAKDOWN,
            note="Spindle fault",
            reported_by_id=creator_id,
            ended_by_id=creator_id,
        )
    )
    await db.commit()

    return {"m1": m1, "m2": m2}


class TestSummary:
    async def test_unfiltered_summary_matches_hand_computed_values(
        self, client, viewer: User, seeded: dict
    ) -> None:
        response = await client.get(
            f"{KPI_BASE}/summary", params=PERIOD, headers=await auth_headers(viewer)
        )
        assert response.status_code == 200
        body = response.json()

        assert body["schedule_adherence"]["value"] == pytest.approx(0.75)
        assert body["schedule_adherence"]["numerator"] == 3
        assert body["schedule_adherence"]["denominator"] == 4

        assert body["on_time_delivery"]["value"] == pytest.approx(0.5)
        assert body["throughput_time"]["median_days"] == pytest.approx(6.5)
        assert body["throughput_time"]["p90_days"] == pytest.approx(6.9)
        assert body["throughput_time"]["count"] == 2

        assert body["first_pass_yield"]["value"] == pytest.approx(25 / 28)
        assert body["scrap_ratio"]["value"] == pytest.approx(2 / 28)
        assert body["rework_ratio"]["value"] == pytest.approx(1 / 28)

        assert body["utilization"]["value"] == pytest.approx(255 / 4800)
        assert body["availability"]["value"] == pytest.approx(4680 / 4800)
        assert body["oee"] == pytest.approx(0.819327731092437)

    async def test_late_lots_has_no_data_for_this_period_gate_but_open_lot_is_separate(
        self, client, viewer: User, seeded: dict
    ) -> None:
        # Lot C (open, never completed) must not leak into any of the
        # completed-lot/completed-order aggregates above. This is a
        # sanity check that the period-scoped summary numerator/
        # denominator counts (asserted above) are exactly 3/4 and 1/2,
        # not inflated by the open lot's single QUEUED order.
        response = await client.get(
            f"{KPI_BASE}/summary", params=PERIOD, headers=await auth_headers(viewer)
        )
        body = response.json()
        assert body["schedule_adherence"]["denominator"] == 4
        assert body["on_time_delivery"]["denominator"] == 2


class TestWeekly:
    async def test_single_week_point_matches_summary(
        self, client, viewer: User, seeded: dict
    ) -> None:
        response = await client.get(
            f"{KPI_BASE}/weekly", params=PERIOD, headers=await auth_headers(viewer)
        )
        assert response.status_code == 200
        points = response.json()["points"]
        assert len(points) == 1
        assert points[0]["iso_week"] == "2026-W10"
        assert points[0]["week_start"] == "2026-03-02"
        assert points[0]["schedule_adherence"]["value"] == pytest.approx(0.75)
        assert points[0]["on_time_delivery"]["value"] == pytest.approx(0.5)


class TestUtilization:
    async def test_per_machine_rows_match_hand_computed_values(
        self, client, viewer: User, seeded: dict
    ) -> None:
        response = await client.get(
            f"{KPI_BASE}/utilization", params=PERIOD, headers=await auth_headers(viewer)
        )
        assert response.status_code == 200
        rows = {row["machine_id"]: row for row in response.json()["rows"]}
        m1_id = seeded["m1"].id
        m2_id = seeded["m2"].id

        assert rows[m1_id]["net_minutes"] == 195
        assert rows[m1_id]["available_minutes"] == 2400
        assert rows[m1_id]["utilization"]["value"] == pytest.approx(195 / 2400)
        assert rows[m1_id]["downtime_minutes"] == 120
        assert rows[m1_id]["availability"]["value"] == pytest.approx(0.95)

        assert rows[m2_id]["net_minutes"] == 60
        assert rows[m2_id]["utilization"]["value"] == pytest.approx(60 / 2400)
        assert rows[m2_id]["downtime_minutes"] == 0
        assert rows[m2_id]["availability"]["value"] == pytest.approx(1.0)

        manual_row = rows[None]
        assert manual_row["net_minutes"] == 0
        assert manual_row["utilization"]["value"] is None
        assert manual_row["availability"] is None


class TestEstimateAccuracy:
    async def test_unfiltered_groups_by_fabrication_method(
        self, client, viewer: User, seeded: dict
    ) -> None:
        response = await client.get(
            f"{KPI_BASE}/estimate-accuracy", params=PERIOD, headers=await auth_headers(viewer)
        )
        assert response.status_code == 200
        rows = {row["fabrication_method_name"]["enGB"]: row for row in response.json()["rows"]}

        assert rows["Milling"]["median_ratio"] == pytest.approx(0.875)
        assert rows["Milling"]["count"] == 1
        assert rows["Deburring"]["median_ratio"] == pytest.approx(1.2)
        assert rows["Deburring"]["count"] == 1
        assert rows["Turning"]["median_ratio"] == pytest.approx(1.25)
        assert rows["Turning"]["count"] == 2

    async def test_machine_filter_drops_the_other_machines_turning_order(
        self, client, viewer: User, seeded: dict
    ) -> None:
        # B1 (Turning, on M2) drops out when filtered to M1, leaving only
        # B2's ratio (30/30 = 1.0) in the "Turning" group.
        params = {**PERIOD, "machine_id": seeded["m1"].id}
        response = await client.get(
            f"{KPI_BASE}/estimate-accuracy", params=params, headers=await auth_headers(viewer)
        )
        rows = {row["fabrication_method_name"]["enGB"]: row for row in response.json()["rows"]}
        assert rows["Turning"]["median_ratio"] == pytest.approx(1.0)
        assert rows["Turning"]["count"] == 1


class TestWaitingTime:
    async def test_internal_group_has_one_day_wait(
        self, client, viewer: User, seeded: dict
    ) -> None:
        response = await client.get(
            f"{KPI_BASE}/waiting-time", params=PERIOD, headers=await auth_headers(viewer)
        )
        assert response.status_code == 200
        rows = {row["position_kind"]: row for row in response.json()["rows"]}
        assert rows["internal"]["median_days"] == pytest.approx(1.0)
        assert rows["internal"]["count"] == 1


class TestLateLots:
    async def test_open_lot_past_target_is_reported_with_its_driver(
        self, client, viewer: User, seeded: dict
    ) -> None:
        response = await client.get(
            f"{KPI_BASE}/late-lots", params=PERIOD, headers=await auth_headers(viewer)
        )
        assert response.status_code == 200
        rows = response.json()["rows"]
        assert len(rows) == 1
        row = rows[0]
        assert row["lot_number"] == "LOT-KPI-C"
        assert row["target_date"] == "2026-03-01"
        assert row["projected_end"] == "2026-03-10"
        assert row["days_late"] == 9
        assert row["driver_reason"] == "missing_material"
        assert row["driver_date"] is None

    async def test_machine_filter_excludes_a_lot_with_no_order_on_that_machine(
        self, client, viewer: User, seeded: dict
    ) -> None:
        # Lot C's only order is on M1, so filtering to M2 must exclude it.
        params = {**PERIOD, "machine_id": seeded["m2"].id}
        response = await client.get(
            f"{KPI_BASE}/late-lots", params=params, headers=await auth_headers(viewer)
        )
        assert response.json()["rows"] == []


class TestQualityByItem:
    async def test_grouped_by_made_item(self, client, viewer: User, seeded: dict) -> None:
        response = await client.get(
            f"{KPI_BASE}/quality-by-item", params=PERIOD, headers=await auth_headers(viewer)
        )
        assert response.status_code == 200
        rows = {
            row["made_item_part_number"] or row["made_item_article_name"]: row
            for row in response.json()["rows"]
        }

        item_a_row = rows["KPI item A"]
        assert item_a_row["completed"] == 20.0
        assert item_a_row["rejected"] == 1.0
        assert item_a_row["rework"] == 1.0
        assert item_a_row["scrap"] == 0.0
        assert item_a_row["yield_ratio"]["value"] == pytest.approx(19 / 20)

        item_b_row = rows["KPI item B"]
        assert item_b_row["completed"] == 8.0
        assert item_b_row["rejected"] == 2.0
        assert item_b_row["rework"] == 0.0
        assert item_b_row["scrap"] == 2.0
        assert item_b_row["yield_ratio"]["value"] == pytest.approx(6 / 8)
