"""
Unit tests for ComputeProductionKpis against fakes, covering the
orchestration this use case adds on top of kpi_rules.py's already
exhaustively tested formulas: resolving which machines a filter covers
(explicit machine, a pool's members, or every active machine), wiring a
fake IProductionKpiRepository's rows through to the response DTOs, and
the late-lots filtering/target-date lookup. The scheduling-context
"dominant driver" resolution (compute_schedule_explanations_for_orders)
is exercised instead by the integration test's "missing_material" case,
not duplicated here with a second scheduling-context fake stack.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from types import SimpleNamespace

from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.entities.machine_pool import MachinePool
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.quality.application.dto.production_kpi_dto import EstimateAccuracyRowResult
from src.modules.quality.application.dto.production_kpi_dto import KpiFilter
from src.modules.quality.application.use_cases.production_kpi.compute_production_kpis import (
    ComputeProductionKpis,
)
from src.modules.quality.domain.services.kpi_rules import CompletedOrderRow
from src.modules.quality.domain.services.kpi_rules import CompletionRow
from src.modules.quality.domain.services.kpi_rules import FabricationMethodRef
from src.modules.quality.domain.services.kpi_rules import WaitingRow
from src.modules.quality.ports.outbound.repositories.production_kpi_repository import (
    CompletedLotRow,
)
from src.modules.quality.ports.outbound.repositories.production_kpi_repository import KpiPeriod
from src.modules.quality.ports.outbound.repositories.production_kpi_repository import KpiScope
from src.modules.quality.ports.outbound.repositories.production_kpi_repository import (
    LateLotCandidateRow,
)
from tests.unit._tenant_settings import TenantSettings

WEEKLY_HOURS = {0: 480, 1: 480, 2: 480, 3: 480, 4: 480, 5: 0, 6: 0}


class FakeKpiRepository:
    def __init__(
        self,
        completed_orders=None,
        completions=None,
        completed_lots=None,
        late_lot_candidates=None,
        waiting_rows=None,
    ):
        self.completed_orders = completed_orders or []
        self.completions = completions or []
        self.completed_lots = completed_lots or []
        self.late_lot_candidates = late_lot_candidates or []
        self.waiting_rows = waiting_rows or []
        self.last_scope: KpiScope | None = None

    async def get_completed_orders(self, period: KpiPeriod, scope: KpiScope):
        self.last_scope = scope
        return self.completed_orders

    async def get_completions(self, period: KpiPeriod, scope: KpiScope):
        self.last_scope = scope
        return self.completions

    async def get_completed_lots(self, period: KpiPeriod, scope: KpiScope):
        self.last_scope = scope
        return self.completed_lots

    async def get_late_lot_candidates(self, scope: KpiScope):
        self.last_scope = scope
        return self.late_lot_candidates

    async def get_waiting_time_rows(self, period: KpiPeriod, scope: KpiScope):
        self.last_scope = scope
        return self.waiting_rows


class FakeMachineRepository:
    def __init__(self, machines: list[ProductionMachine]):
        self._machines = machines

    async def get_all(self) -> list[ProductionMachine]:
        return self._machines


class FakePoolRepository:
    def __init__(self, pools_by_id: dict[int, MachinePool]):
        self._pools = pools_by_id

    async def get_by_id(self, id: int) -> MachinePool | None:
        return self._pools.get(id)

    async def get_by_ids(self, ids: list[int]) -> list:
        found = [await self.get_by_id(i) for i in ids]
        return [item for item in found if item is not None]


class FakeCalendarRepository:
    async def get_working_hours_by_machine_ids(self, machine_ids):
        return []

    async def get_exceptions_by_machine_ids(self, machine_ids):
        return []

    async def get_holidays(self) -> list:
        return []


class FakeSettingsRepository:
    async def get_production(self) -> AdminProductionSettings:
        return AdminProductionSettings(
            id=1,
            production_order_number_format="PON-{yy}-{seq:05d}",
            default_weekly_hours=WEEKLY_HOURS,
            default_external_lead_days=0,
            response_time_days=1,
            require_qa=False,
        )

    async def get_general(self) -> SimpleNamespace:
        # Only the tenant timezone is read; UTC keeps calendar hours in UTC.
        return SimpleNamespace(default_timezone="UTC")


class FakeDowntimeRepository:
    def __init__(self, minutes_by_machine: dict[int, int] | None = None):
        self._minutes = minutes_by_machine or {}

    async def minutes_by_machine_in_period(self, machine_ids, start, end):
        return {mid: minutes for mid, minutes in self._minutes.items() if mid in machine_ids}


class FakeLotRepository:
    def __init__(self, lots: list[ProductionLot]):
        self._lots = {lot.id: lot for lot in lots}

    async def get_by_ids(self, ids: list[int]) -> list[ProductionLot]:
        return [self._lots[i] for i in ids if i in self._lots]


class _UnusedRepo:
    """Stand-in for a SchedulingRepos member no test in this file ever
    calls (target dates are always resolved via ProductionLot.
    required_delivery_date here, which short-circuits before any of
    these would be touched)."""

    def __getattr__(self, name):
        raise AssertionError(f"unexpected call: {name}")


def _machine(machine_id: int, *, archived: bool = False) -> ProductionMachine:
    return ProductionMachine(
        id=machine_id,
        created=datetime.now(UTC).date(),
        changed=None,
        changes=[],
        archived=archived,
        internal_name=f"M{machine_id}",
        vendor="Contoso",
        model="VF-2",
        fabrication_method_ids=[],
        max_part_dimension=None,
        note=None,
        creator_id=1,
    )


def _use_case(
    kpi_repo=None,
    machines=None,
    pools=None,
    downtime=None,
    lots=None,
) -> ComputeProductionKpis:
    repos = SchedulingRepos(
        orders=_UnusedRepo(),
        lots=FakeLotRepository(lots or []),
        order_items=_UnusedRepo(),
        source_item_demands=_UnusedRepo(),
        source_item_allocations=_UnusedRepo(),
        made_item_allocations=_UnusedRepo(),
        made_item_demands=_UnusedRepo(),
        settings=TenantSettings(),
    )
    return ComputeProductionKpis(
        kpi_repo=kpi_repo or FakeKpiRepository(),
        scheduling_repos=repos,
        machine_repo=FakeMachineRepository(machines or []),
        pool_repo=FakePoolRepository(pools or {}),
        calendar_repo=FakeCalendarRepository(),
        settings_repo=FakeSettingsRepository(),
        downtime_repo=FakeDowntimeRepository(downtime),
    )


def _lot(lot_id: int, *, required_delivery_date=None, completed_at=None) -> ProductionLot:
    return ProductionLot(
        id=lot_id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=None,
        changes=[],
        lot_number=f"LOT-{lot_id}",
        quantity=1.0,
        status=LotStatus.PLANNED,
        priority=UrgencyClass.NORMAL,
        note=None,
        creator_id=1,
        made_item_id=1,
        project_id=1,
        input_demand_id=None,
        required_delivery_date=required_delivery_date,
        completed_at=completed_at,
    )


class TestResolveMachineIds:
    async def test_explicit_machine_id_wins(self):
        machine = _machine(1)
        use_case = _use_case(kpi_repo=FakeKpiRepository(), machines=[machine], downtime={})
        kpi_filter = KpiFilter(date_from=date(2026, 3, 2), date_to=date(2026, 3, 2), machine_id=1)
        result = await use_case.utilization(kpi_filter)
        assert [row.machine_id for row in result.rows if row.machine_id is not None] == [1]

    async def test_pool_resolves_to_its_members(self):
        machines = [_machine(1), _machine(2), _machine(3)]
        pool = MachinePool(
            id=5,
            created=date(2026, 1, 1),
            changed=None,
            changes=[],
            archived=False,
            name="Pool",
            machine_ids=[1, 2],
            note=None,
            creator_id=1,
        )
        use_case = _use_case(machines=machines, pools={5: pool}, downtime={})
        kpi_filter = KpiFilter(
            date_from=date(2026, 3, 2), date_to=date(2026, 3, 2), machine_pool_id=5
        )
        result = await use_case.utilization(kpi_filter)
        machine_ids = sorted(row.machine_id for row in result.rows if row.machine_id is not None)
        assert machine_ids == [1, 2]

    async def test_no_filter_uses_every_active_machine(self):
        machines = [_machine(1), _machine(2, archived=True)]
        use_case = _use_case(machines=machines, downtime={})
        kpi_filter = KpiFilter(date_from=date(2026, 3, 2), date_to=date(2026, 3, 2))
        result = await use_case.utilization(kpi_filter)
        machine_ids = sorted(row.machine_id for row in result.rows if row.machine_id is not None)
        assert machine_ids == [1]  # the archived machine is excluded


class TestUtilizationWiring:
    async def test_net_minutes_and_downtime_flow_through_to_the_response(self):
        machine = _machine(1)
        order = CompletedOrderRow(
            order_id=1,
            machine_id=1,
            lot_id=1,
            actual_start=datetime(2026, 3, 2, 8, tzinfo=UTC),
            actual_end=datetime(2026, 3, 2, 9, tzinfo=UTC),
            planned_end_at_start=None,
            estimated_duration_minutes=60,
            interruptions=(),
            fabrication_methods=(),
        )
        use_case = _use_case(
            kpi_repo=FakeKpiRepository(completed_orders=[order]),
            machines=[machine],
            downtime={1: 30},
        )
        kpi_filter = KpiFilter(date_from=date(2026, 3, 2), date_to=date(2026, 3, 2), machine_id=1)
        result = await use_case.utilization(kpi_filter)
        row = next(r for r in result.rows if r.machine_id == 1)
        assert row.net_minutes == 60
        assert row.available_minutes == 480
        assert row.downtime_minutes == 30
        assert row.utilization.value == 60 / 480
        assert row.availability.value == (480 - 30) / 480


class TestEstimateAccuracyAndWaitingTimeAndQualityByItemWiring:
    async def test_estimate_accuracy_delegates_to_kpi_rules(self):
        order = CompletedOrderRow(
            order_id=1,
            machine_id=1,
            lot_id=1,
            actual_start=datetime(2026, 3, 2, 8, tzinfo=UTC),
            actual_end=datetime(2026, 3, 2, 9, tzinfo=UTC),
            planned_end_at_start=None,
            estimated_duration_minutes=30,
            interruptions=(),
            fabrication_methods=(FabricationMethodRef(9, LocalizedText({"enGB": "Welding"})),),
        )
        use_case = _use_case(kpi_repo=FakeKpiRepository(completed_orders=[order]))
        kpi_filter = KpiFilter(date_from=date(2026, 3, 2), date_to=date(2026, 3, 2))
        result = await use_case.estimate_accuracy(kpi_filter)
        assert result.rows == [
            EstimateAccuracyRowResult(
                fabrication_method_id=9,
                fabrication_method_name={"enGB": "Welding"},
                median_ratio=2.0,
                count=1,
            )
        ]

    async def test_waiting_time_delegates_to_kpi_rules(self):
        row = WaitingRow(
            order_id=1,
            position_kind="internal",
            actual_start=datetime(2026, 3, 5, tzinfo=UTC),
            predecessor_ready=date(2026, 3, 3),
        )
        use_case = _use_case(kpi_repo=FakeKpiRepository(waiting_rows=[row]))
        kpi_filter = KpiFilter(date_from=date(2026, 3, 2), date_to=date(2026, 3, 6))
        result = await use_case.waiting_time(kpi_filter)
        assert len(result.rows) == 1
        assert result.rows[0].position_kind == "internal"
        assert result.rows[0].median_days == 2.0
        assert result.rows[0].count == 1

    async def test_quality_by_item_delegates_to_kpi_rules(self):
        completion = CompletionRow(
            completion_id=1,
            made_item_id=7,
            made_item_part_number="PN-7",
            made_item_article_name="Widget",
            quantity=10.0,
            quantity_accepted=8.0,
            quantity_rejected=2.0,
            quantity_rework=0.0,
            quantity_scrap=2.0,
        )
        use_case = _use_case(kpi_repo=FakeKpiRepository(completions=[completion]))
        kpi_filter = KpiFilter(date_from=date(2026, 3, 2), date_to=date(2026, 3, 6))
        result = await use_case.quality_by_item(kpi_filter)
        assert len(result.rows) == 1
        row = result.rows[0]
        assert row.made_item_id == 7
        assert row.completed == 10.0
        assert row.scrap == 2.0
        assert row.yield_ratio.value == 0.8


class TestLateLots:
    async def test_lot_past_target_with_no_resolvable_order_has_no_driver(self):
        lot = _lot(1, required_delivery_date=date(2026, 3, 1))
        candidate = LateLotCandidateRow(
            lot_id=1, latest_order_id=None, effective_end=datetime(2026, 3, 5, tzinfo=UTC)
        )
        use_case = _use_case(
            kpi_repo=FakeKpiRepository(late_lot_candidates=[candidate]), lots=[lot]
        )
        kpi_filter = KpiFilter(date_from=date(2026, 3, 2), date_to=date(2026, 3, 6))
        result = await use_case.late_lots(kpi_filter)
        assert len(result.rows) == 1
        row = result.rows[0]
        assert row.lot_number == "LOT-1"
        assert row.target_date == date(2026, 3, 1)
        assert row.projected_end == date(2026, 3, 5)
        assert row.days_late == 4
        assert row.driver_reason is None
        assert row.driver_date is None

    async def test_lot_not_past_target_is_excluded(self):
        lot = _lot(1, required_delivery_date=date(2026, 3, 10))
        candidate = LateLotCandidateRow(
            lot_id=1, latest_order_id=None, effective_end=datetime(2026, 3, 5, tzinfo=UTC)
        )
        use_case = _use_case(
            kpi_repo=FakeKpiRepository(late_lot_candidates=[candidate]), lots=[lot]
        )
        kpi_filter = KpiFilter(date_from=date(2026, 3, 2), date_to=date(2026, 3, 6))
        result = await use_case.late_lots(kpi_filter)
        assert result.rows == []

    async def test_no_candidates_short_circuits_without_touching_lots(self):
        use_case = _use_case(kpi_repo=FakeKpiRepository(late_lot_candidates=[]))
        kpi_filter = KpiFilter(date_from=date(2026, 3, 2), date_to=date(2026, 3, 6))
        result = await use_case.late_lots(kpi_filter)
        assert result.rows == []


class TestCompletedLotRowsFeedThroughDescribeTargetDates:
    async def test_summary_on_time_delivery_uses_the_lots_own_required_delivery_date(self):
        lot_row = CompletedLotRow(
            lot_id=1,
            lot_number="LOT-1",
            created=datetime(2026, 2, 20, tzinfo=UTC),
            completed_at=datetime(2026, 3, 3, tzinfo=UTC),
        )
        lot = _lot(
            1,
            required_delivery_date=date(2026, 3, 4),
            completed_at=datetime(2026, 3, 3, tzinfo=UTC),
        )
        use_case = _use_case(
            kpi_repo=FakeKpiRepository(completed_lots=[lot_row]), lots=[lot], downtime={}
        )
        kpi_filter = KpiFilter(date_from=date(2026, 3, 2), date_to=date(2026, 3, 6))
        result = await use_case.summary(kpi_filter)
        assert result.on_time_delivery.value == 1.0
        assert result.throughput_time.count == 1
