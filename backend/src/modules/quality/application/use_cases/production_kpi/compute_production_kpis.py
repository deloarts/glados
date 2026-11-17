"""
Read-only production KPI use case: one method per endpoint
(v1/web/endpoints/production_kpi.py), each gathering the bounded rows the
period/scope needs through IProductionKpiRepository plus the existing
scheduling repositories and calendar builder, then applying the pure
formulas in src.modules.quality.domain.services.kpi_rules. No permission check here,
mirroring GetScheduleBoard: read access is whatever the route's plain
authentication already requires, nothing more specific.
"""

from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta
from datetime import tzinfo

from src.modules.fulfillment.api import IFulfillmentSettingsRepository
from src.modules.fulfillment.application.facade.scheduling import IMachineCalendarRepository
from src.modules.fulfillment.application.facade.scheduling import IMachinePoolRepository
from src.modules.fulfillment.application.facade.scheduling import IProductionMachineRepository
from src.modules.fulfillment.application.facade.scheduling import SchedulingRepos
from src.modules.fulfillment.application.facade.scheduling import TargetDateSource
from src.modules.fulfillment.application.facade.scheduling import build_machine_calendars
from src.modules.fulfillment.application.facade.scheduling import (
    compute_schedule_explanations_for_orders,
)
from src.modules.fulfillment.application.facade.scheduling import describe_lot_target_dates
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.policies.scheduling import EarliestStartExplanation
from src.modules.fulfillment.ports.outbound.fulfillment_queries import IMachineDowntimeQueries
from src.modules.platform.application.services.tenant_timezone import tenant_zone
from src.modules.quality.application.dto.production_kpi_dto import KpiFilter
from src.modules.quality.application.dto.production_kpi_dto import LateLotResult
from src.modules.quality.application.dto.production_kpi_dto import (
    ProductionKpiEstimateAccuracyResult,
)
from src.modules.quality.application.dto.production_kpi_dto import ProductionKpiLateLotsResult
from src.modules.quality.application.dto.production_kpi_dto import ProductionKpiQualityByItemResult
from src.modules.quality.application.dto.production_kpi_dto import (
    ProductionKpiRejectedPerSupplierResult,
)
from src.modules.quality.application.dto.production_kpi_dto import ProductionKpiScrapByReasonResult
from src.modules.quality.application.dto.production_kpi_dto import ProductionKpiSummaryResult
from src.modules.quality.application.dto.production_kpi_dto import ProductionKpiUtilizationResult
from src.modules.quality.application.dto.production_kpi_dto import ProductionKpiWaitingTimeResult
from src.modules.quality.application.dto.production_kpi_dto import ProductionKpiWeeklyResult
from src.modules.quality.application.mappers import production_kpi_mapper as mapper
from src.modules.quality.domain.services import kpi_rules
from src.modules.quality.ports.outbound.repositories.production_kpi_repository import (
    CompletedLotRow,
)
from src.modules.quality.ports.outbound.repositories.production_kpi_repository import (
    IProductionKpiRepository,
)
from src.modules.quality.ports.outbound.repositories.production_kpi_repository import KpiPeriod
from src.modules.quality.ports.outbound.repositories.production_kpi_repository import KpiScope
from src.modules.quality.ports.outbound.repositories.production_kpi_repository import (
    LateLotCandidateRow,
)


def _period_bounds(period: KpiPeriod) -> tuple[datetime, datetime]:
    """The same "[from, to] inclusive days" -> half-open instant
    conversion adapters.outbound.persistence.date_range applies, in the
    period's zone, kept local rather than imported since the application
    layer must not depend on the persistence adapter layer."""
    start = datetime.combine(period.date_from, time.min, tzinfo=period.zone)
    end = datetime.combine(period.date_to + timedelta(days=1), time.min, tzinfo=period.zone)
    return start, end


def _dates_in_period(period: KpiPeriod) -> list[date]:
    span = (period.date_to - period.date_from).days
    return [period.date_from + timedelta(days=i) for i in range(span + 1)]


class ComputeProductionKpis:
    def __init__(
        self,
        kpi_repo: IProductionKpiRepository,
        scheduling_repos: SchedulingRepos,
        machine_repo: IProductionMachineRepository,
        pool_repo: IMachinePoolRepository,
        calendar_repo: IMachineCalendarRepository,
        settings_repo: IFulfillmentSettingsRepository,
        downtime_repo: IMachineDowntimeQueries,
    ) -> None:
        self._kpi_repo = kpi_repo
        self._repos = scheduling_repos
        self._machines = machine_repo
        self._pools = pool_repo
        self._calendars = calendar_repo
        self._settings = settings_repo
        self._downtimes = downtime_repo

    # ── Shared building blocks ───────────────────────────────────────

    async def _period(self, kpi_filter: KpiFilter) -> KpiPeriod:
        """The filter's days, read in the tenant's timezone like every
        other calendar day in the app."""
        return KpiPeriod(
            date_from=kpi_filter.date_from,
            date_to=kpi_filter.date_to,
            zone=await tenant_zone(self._settings),
        )

    def _scope(self, kpi_filter: KpiFilter) -> KpiScope:
        return KpiScope(
            machine_id=kpi_filter.machine_id,
            machine_pool_id=kpi_filter.machine_pool_id,
            project_id=kpi_filter.project_id,
            customer_id=kpi_filter.customer_id,
        )

    async def _resolve_machine_ids(
        self, kpi_filter: KpiFilter
    ) -> tuple[list[int], list[ProductionMachine] | None]:
        """Which machines the utilization/availability figures cover: one
        explicit machine, a pool's members, or every active machine when
        neither filter narrows it down. Also returns every machine when it
        had to load them, so the capacity rows reuse that load."""
        if kpi_filter.machine_id is not None:
            return [kpi_filter.machine_id], None
        if kpi_filter.machine_pool_id is not None:
            pool = await self._pools.get_by_id(kpi_filter.machine_pool_id)
            return (list(pool.machine_ids) if pool else []), None
        machines = await self._machines.get_all()
        return [machine.id for machine in machines if not machine.archived], machines

    async def _capacity_rows(
        self,
        machine_ids: list[int],
        period: KpiPeriod,
        machines: list[ProductionMachine] | None,
    ) -> list[kpi_rules.CapacityRow]:
        if not machine_ids:
            return []
        settings = await self._settings.get_production()
        calendars = await build_machine_calendars(
            machine_ids,
            self._calendars,
            settings.default_weekly_hours,
            zone=period.zone,
        )
        if machines is None:
            machines = await self._machines.get_all()
        machines_by_id = {machine.id: machine for machine in machines}
        dates = _dates_in_period(period)
        rows = []
        for machine_id in machine_ids:
            calendar = calendars.get(machine_id)
            if calendar is None:
                continue
            available = sum(calendar.minutes_available_on(d) for d in dates)
            machine = machines_by_id.get(machine_id)
            rows.append(
                kpi_rules.CapacityRow(
                    machine_id=machine_id,
                    machine_internal_name=machine.internal_name if machine else "",
                    available_minutes=available,
                )
            )
        return rows

    async def _downtime_rows(
        self, machine_ids: list[int], period: KpiPeriod
    ) -> list[kpi_rules.DowntimeRow]:
        if not machine_ids:
            return []
        start, end = _period_bounds(period)
        minutes_by_machine = await self._downtimes.minutes_by_machine_in_period(
            machine_ids, start, end
        )
        return [
            kpi_rules.DowntimeRow(machine_id=machine_id, minutes=minutes)
            for machine_id, minutes in minutes_by_machine.items()
        ]

    async def _lot_rows_with_target_dates(
        self, completed_lots: list[CompletedLotRow]
    ) -> list[kpi_rules.LotRow]:
        if not completed_lots:
            return []
        lots = await self._repos.lots.get_by_ids([row.lot_id for row in completed_lots])
        target_dates = await describe_lot_target_dates(lots, self._repos)
        return [
            kpi_rules.LotRow(
                lot_id=row.lot_id,
                lot_number=row.lot_number,
                created=row.created,
                completed_at=row.completed_at,
                target_date=target_dates.get(row.lot_id, (None, None, None))[0],
            )
            for row in completed_lots
        ]

    # ── Endpoints ─────────────────────────────────────────────────────

    async def summary(self, kpi_filter: KpiFilter) -> ProductionKpiSummaryResult:
        period = await self._period(kpi_filter)
        scope = self._scope(kpi_filter)
        orders = await self._kpi_repo.get_completed_orders(period, scope)
        completions = await self._kpi_repo.get_completions(period, scope)
        lots = await self._lot_rows_with_target_dates(
            await self._kpi_repo.get_completed_lots(period, scope)
        )

        machine_ids, machines = await self._resolve_machine_ids(kpi_filter)
        capacity = await self._capacity_rows(machine_ids, period, machines)
        downtime = await self._downtime_rows(machine_ids, period)
        utilization_rows = kpi_rules.compute_utilization(orders, capacity)
        availability_rows = kpi_rules.compute_availability(capacity, downtime)

        overall_utilization = kpi_rules.ratio(
            sum(row.ratio.numerator for row in utilization_rows if row.machine_id is not None),
            sum(row.ratio.denominator for row in utilization_rows if row.machine_id is not None),
        )
        overall_availability = kpi_rules.ratio(
            sum(row.ratio.numerator for row in availability_rows),
            sum(row.ratio.denominator for row in availability_rows),
        )
        first_pass_yield = kpi_rules.compute_first_pass_yield(completions)
        performance = kpi_rules.compute_performance(orders)
        oee = kpi_rules.compute_oee(
            overall_availability, overall_utilization, first_pass_yield, performance
        )

        return ProductionKpiSummaryResult(
            schedule_adherence=mapper.to_ratio_result(kpi_rules.compute_schedule_adherence(orders)),
            on_time_delivery=mapper.to_ratio_result(
                kpi_rules.compute_on_time_delivery(lots, period.zone)
            ),
            throughput_time=mapper.to_throughput_result(kpi_rules.compute_throughput_time(lots)),
            first_pass_yield=mapper.to_ratio_result(first_pass_yield),
            scrap_ratio=mapper.to_ratio_result(kpi_rules.compute_scrap_ratio(completions)),
            rework_ratio=mapper.to_ratio_result(kpi_rules.compute_rework_ratio(completions)),
            utilization=mapper.to_ratio_result(overall_utilization)
            if overall_utilization.value is not None
            else None,
            availability=mapper.to_ratio_result(overall_availability)
            if overall_availability.value is not None
            else None,
            oee=oee,
        )

    async def weekly(self, kpi_filter: KpiFilter) -> ProductionKpiWeeklyResult:
        period = await self._period(kpi_filter)
        scope = self._scope(kpi_filter)
        orders = await self._kpi_repo.get_completed_orders(period, scope)
        lots = await self._lot_rows_with_target_dates(
            await self._kpi_repo.get_completed_lots(period, scope)
        )
        points = kpi_rules.compute_weekly_series(
            orders, lots, kpi_filter.date_from, kpi_filter.date_to, period.zone
        )
        return ProductionKpiWeeklyResult(
            points=[mapper.to_weekly_point_result(point) for point in points]
        )

    async def utilization(self, kpi_filter: KpiFilter) -> ProductionKpiUtilizationResult:
        period = await self._period(kpi_filter)
        scope = self._scope(kpi_filter)
        orders = await self._kpi_repo.get_completed_orders(period, scope)
        machine_ids, machines = await self._resolve_machine_ids(kpi_filter)
        capacity = await self._capacity_rows(machine_ids, period, machines)
        downtime = await self._downtime_rows(machine_ids, period)
        utilization_rows = kpi_rules.compute_utilization(orders, capacity)
        availability_by_machine = {
            row.machine_id: row for row in kpi_rules.compute_availability(capacity, downtime)
        }
        return ProductionKpiUtilizationResult(
            rows=[
                mapper.to_utilization_row_result(
                    row,
                    availability_by_machine.get(row.machine_id)
                    if row.machine_id is not None
                    else None,
                )
                for row in utilization_rows
            ]
        )

    async def estimate_accuracy(self, kpi_filter: KpiFilter) -> ProductionKpiEstimateAccuracyResult:
        period = await self._period(kpi_filter)
        scope = self._scope(kpi_filter)
        orders = await self._kpi_repo.get_completed_orders(period, scope)
        rows = kpi_rules.compute_estimate_accuracy(orders)
        return ProductionKpiEstimateAccuracyResult(
            rows=[mapper.to_estimate_accuracy_row_result(row) for row in rows]
        )

    async def waiting_time(self, kpi_filter: KpiFilter) -> ProductionKpiWaitingTimeResult:
        period = await self._period(kpi_filter)
        scope = self._scope(kpi_filter)
        rows = await self._kpi_repo.get_waiting_time_rows(period, scope)
        results = kpi_rules.compute_waiting_time(rows, period.zone)
        return ProductionKpiWaitingTimeResult(
            rows=[mapper.to_waiting_time_row_result(row) for row in results]
        )

    async def quality_by_item(self, kpi_filter: KpiFilter) -> ProductionKpiQualityByItemResult:
        period = await self._period(kpi_filter)
        scope = self._scope(kpi_filter)
        completions = await self._kpi_repo.get_completions(period, scope)
        rows = kpi_rules.compute_quality_by_item(completions)
        return ProductionKpiQualityByItemResult(
            rows=[mapper.to_quality_by_item_row_result(row) for row in rows]
        )

    async def scrap_by_reason(self, kpi_filter: KpiFilter) -> ProductionKpiScrapByReasonResult:
        period = await self._period(kpi_filter)
        scope = self._scope(kpi_filter)
        events = await self._kpi_repo.get_scrap_events(period, scope)
        rows = kpi_rules.scrap_by_reason(events)
        return ProductionKpiScrapByReasonResult(
            rows=[mapper.to_scrap_by_reason_row_result(row) for row in rows]
        )

    async def rejected_per_supplier(
        self, kpi_filter: KpiFilter
    ) -> ProductionKpiRejectedPerSupplierResult:
        period = await self._period(kpi_filter)
        scope = self._scope(kpi_filter)
        deliveries = await self._kpi_repo.get_supplier_deliveries(period, scope)
        rows = kpi_rules.rejected_per_supplier(deliveries)
        return ProductionKpiRejectedPerSupplierResult(
            rows=[mapper.to_rejected_per_supplier_row_result(row) for row in rows]
        )

    async def late_lots(self, kpi_filter: KpiFilter) -> ProductionKpiLateLotsResult:
        """Open lots is a point-in-time state, not a period aggregate, so
        this endpoint ignores kpi_filter.date_from/date_to and only
        applies the machine/pool/project/customer scope."""
        scope = self._scope(kpi_filter)
        candidates = await self._kpi_repo.get_late_lot_candidates(scope)
        if not candidates:
            return ProductionKpiLateLotsResult(rows=[])

        lots = await self._repos.lots.get_by_ids([candidate.lot_id for candidate in candidates])
        lots_by_id = {lot.id: lot for lot in lots}
        target_dates = await describe_lot_target_dates(lots, self._repos)

        zone = await tenant_zone(self._settings)
        late_candidates = self._filter_late_candidates(candidates, target_dates, zone)
        if not late_candidates:
            return ProductionKpiLateLotsResult(rows=[])

        explanations = await self._resolve_late_lot_explanations(late_candidates, lots_by_id)
        rows = self._build_late_lot_rows(
            late_candidates, lots_by_id, target_dates, explanations, zone
        )
        rows.sort(key=lambda row: row.days_late, reverse=True)
        return ProductionKpiLateLotsResult(rows=rows)

    def _filter_late_candidates(
        self,
        candidates: list[LateLotCandidateRow],
        target_dates: dict[int, tuple[date | None, TargetDateSource | None, int | None]],
        zone: tzinfo,
    ) -> list[LateLotCandidateRow]:
        return [
            candidate
            for candidate in candidates
            if kpi_rules.is_lot_late(
                candidate.effective_end,
                target_dates.get(candidate.lot_id, (None, None, None))[0],
                zone,
            )
        ]

    async def _resolve_late_lot_explanations(
        self,
        late_candidates: list[LateLotCandidateRow],
        lots_by_id: dict[int, ProductionLot],
    ) -> dict[int, EarliestStartExplanation]:
        order_ids = [c.latest_order_id for c in late_candidates if c.latest_order_id is not None]
        if not order_ids:
            return {}
        orders = await self._repos.orders.get_by_ids(order_ids)
        if not orders:
            return {}
        return await compute_schedule_explanations_for_orders(
            orders, self._repos, self._machines, lots_by_id, self._pools
        )

    def _build_late_lot_rows(
        self,
        late_candidates: list[LateLotCandidateRow],
        lots_by_id: dict[int, ProductionLot],
        target_dates: dict[int, tuple[date | None, TargetDateSource | None, int | None]],
        explanations: dict[int, EarliestStartExplanation],
        zone: tzinfo,
    ) -> list[LateLotResult]:
        rows: list[LateLotResult] = []
        for candidate in late_candidates:
            lot = lots_by_id.get(candidate.lot_id)
            target_date = target_dates.get(candidate.lot_id, (None, None, None))[0]
            if lot is None or target_date is None or candidate.effective_end is None:
                continue
            explanation = (
                explanations.get(candidate.latest_order_id)
                if candidate.latest_order_id is not None
                else None
            )
            projected_end = candidate.effective_end.astimezone(zone).date()
            rows.append(
                LateLotResult(
                    lot_id=lot.id,
                    lot_number=lot.lot_number,
                    target_date=target_date,
                    projected_end=projected_end,
                    days_late=(projected_end - target_date).days,
                    driver_reason=explanation.reason if explanation else None,
                    driver_date=explanation.date if explanation else None,
                )
            )
        return rows
