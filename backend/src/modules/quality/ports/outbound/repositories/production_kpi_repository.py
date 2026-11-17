"""
Repository interface for the production KPI use case's bounded, batched
queries. Every method is scoped by a period and the same optional
machine/pool/project/customer filter, and returns the plain rows
kpi_rules.py's pure formulas consume, never ORM rows or ratios.
"""

from dataclasses import dataclass
from datetime import date
from datetime import datetime
from datetime import tzinfo
from typing import Protocol
from typing import runtime_checkable

from src.modules.quality.domain.services.kpi_rules import CompletedOrderRow
from src.modules.quality.domain.services.kpi_rules import CompletionRow
from src.modules.quality.domain.services.kpi_rules import ScrapReasonRow
from src.modules.quality.domain.services.kpi_rules import SupplierDeliveryRow
from src.modules.quality.domain.services.kpi_rules import WaitingRow


@dataclass(frozen=True)
class KpiPeriod:
    """The inclusive calendar days a KPI covers. The days are the tenant's,
    so `zone` turns them into instants and an instant into its day."""

    date_from: date
    date_to: date
    zone: tzinfo


@dataclass(frozen=True)
class KpiScope:
    """Optional filter dimensions shared by every KPI endpoint. All four
    are independent and may combine; None means "no restriction" on that
    dimension."""

    machine_id: int | None = None
    machine_pool_id: int | None = None
    project_id: int | None = None
    customer_id: int | None = None


@dataclass(frozen=True)
class CompletedLotRow:
    """One ProductionLot with completed_at inside the requested period.
    Target date resolution happens in the application layer (see
    _context.describe_lot_target_dates), this row only carries what the
    query itself can answer."""

    lot_id: int
    lot_number: str
    created: datetime
    completed_at: datetime


@dataclass(frozen=True)
class LateLotCandidateRow:
    """One open (non-terminal) lot's latest order, "latest" meaning the
    order among the lot's own whose effective end (actual_end once it has
    finished, else its current planned_end) is furthest out.
    latest_order_id/effective_end are both None for a lot with no orders
    at all yet (e.g. still DRAFT)."""

    lot_id: int
    latest_order_id: int | None
    effective_end: datetime | None


@runtime_checkable
class IProductionKpiRepository(Protocol):
    async def get_completed_orders(
        self, period: KpiPeriod, scope: KpiScope
    ) -> list[CompletedOrderRow]:
        """Every ProductionOrder with status=completed and actual_end inside
        the period, matching scope, each with its interruptions and its
        lot position's fabrication methods already joined. The one
        dataset behind schedule adherence, utilization, estimate accuracy
        and the OEE performance factor."""
        ...

    async def get_completions(self, period: KpiPeriod, scope: KpiScope) -> list[CompletionRow]:
        """Every ProductionOrderCompletion with completion_date inside the
        period, matching scope, denormalized with the made item it
        completes work on."""
        ...

    async def get_completed_lots(self, period: KpiPeriod, scope: KpiScope) -> list[CompletedLotRow]:
        """Every ProductionLot with completed_at inside the period,
        matching scope."""
        ...

    async def get_late_lot_candidates(self, scope: KpiScope) -> list[LateLotCandidateRow]:
        """Every open lot matching scope (no period, lateness is a
        point-in-time state, not a period aggregate), with its latest
        order already resolved."""
        ...

    async def get_waiting_time_rows(self, period: KpiPeriod, scope: KpiScope) -> list[WaitingRow]:
        """Every order with actual_start inside the period, matching
        scope, whose lot position has a predecessor position, with that
        predecessor's readiness already resolved."""
        ...

    async def get_scrap_events(self, period: KpiPeriod, scope: KpiScope) -> list[ScrapReasonRow]:
        """Every scrapped-pieces event inside the period: a completion
        with quantity_scrap > 0 (full machine/pool/project/customer
        scope, mirroring get_completed_orders) and a delivery rejection
        with outcome lost (project/customer scope only, a goods-receipt
        rejection has no machine or pool of its own to filter on). An
        event with no classified reason is left out."""
        ...

    async def get_supplier_deliveries(
        self, period: KpiPeriod, scope: KpiScope
    ) -> list[SupplierDeliveryRow]:
        """Every order item delivery record inside the period, matching
        the project/customer scope (machine/pool scope is not applied,
        same reasoning as the delivery half of get_scrap_events)."""
        ...
