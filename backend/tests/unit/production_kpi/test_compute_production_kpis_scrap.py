"""
Unit tests for ComputeProductionKpis.scrap_by_reason and
.rejected_per_supplier against a fake IProductionKpiRepository, covering
the wiring from the repository's rows through kpi_rules.py's pure
formulas to the response DTOs. Both methods read the tenant timezone
from the settings; every other collaborator ComputeProductionKpis takes
is untouched by either method, so this file uses bare stand-ins that
raise if ever called, the same idiom test_compute_production_kpis.py's
own _UnusedRepo uses.
"""

from types import SimpleNamespace

from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.quality.application.dto.production_kpi_dto import KpiFilter
from src.modules.quality.application.use_cases.production_kpi.compute_production_kpis import (
    ComputeProductionKpis,
)
from src.modules.quality.domain.services.kpi_rules import ScrapReasonRow
from src.modules.quality.domain.services.kpi_rules import SupplierDeliveryRow
from src.modules.quality.ports.outbound.repositories.production_kpi_repository import KpiPeriod
from src.modules.quality.ports.outbound.repositories.production_kpi_repository import KpiScope
from tests.unit._tenant_settings import TenantSettings


class _Unused:
    """Stand-in for a collaborator neither method under test ever calls."""

    def __getattr__(self, name: str):
        raise AssertionError(f"unexpected call: {name}")


class _TimezoneOnlySettings:
    """Settings stand-in that answers only the tenant timezone."""

    async def get_general(self) -> SimpleNamespace:
        return SimpleNamespace(default_timezone="UTC")


class FakeKpiRepository:
    def __init__(self, scrap_events=None, supplier_deliveries=None):
        self.scrap_events = scrap_events or []
        self.supplier_deliveries = supplier_deliveries or []
        self.last_period: KpiPeriod | None = None
        self.last_scope: KpiScope | None = None

    async def get_scrap_events(self, period: KpiPeriod, scope: KpiScope):
        self.last_period = period
        self.last_scope = scope
        return self.scrap_events

    async def get_supplier_deliveries(self, period: KpiPeriod, scope: KpiScope):
        self.last_period = period
        self.last_scope = scope
        return self.supplier_deliveries


def _use_case(kpi_repo: FakeKpiRepository) -> ComputeProductionKpis:
    return ComputeProductionKpis(
        kpi_repo=kpi_repo,  # type: ignore[arg-type]
        scheduling_repos=SchedulingRepos(
            orders=_Unused(),  # type: ignore[arg-type]
            lots=_Unused(),  # type: ignore[arg-type]
            order_items=_Unused(),  # type: ignore[arg-type]
            source_item_demands=_Unused(),  # type: ignore[arg-type]
            source_item_allocations=_Unused(),  # type: ignore[arg-type]
            made_item_allocations=_Unused(),  # type: ignore[arg-type]
            made_item_demands=_Unused(),  # type: ignore[arg-type]
            settings=TenantSettings(),  # type: ignore[arg-type]
        ),
        machine_repo=_Unused(),  # type: ignore[arg-type]
        pool_repo=_Unused(),  # type: ignore[arg-type]
        calendar_repo=_Unused(),  # type: ignore[arg-type]
        settings_repo=_TimezoneOnlySettings(),  # type: ignore[arg-type]
        downtime_repo=_Unused(),  # type: ignore[arg-type]
    )


def _filter(**overrides) -> KpiFilter:
    base = {
        "date_from": "2026-03-01",
        "date_to": "2026-03-31",
        "machine_id": None,
        "machine_pool_id": None,
        "project_id": None,
        "customer_id": None,
    }
    base.update(overrides)
    return KpiFilter(**base)


class TestScrapByReason:
    async def test_empty_repository_yields_empty_rows(self) -> None:
        use_case = _use_case(FakeKpiRepository())
        result = await use_case.scrap_by_reason(_filter())
        assert result.rows == []

    async def test_wires_repository_rows_through_kpi_rules(self) -> None:
        repo = FakeKpiRepository(
            scrap_events=[
                ScrapReasonRow(quantity=2.0, reason="tool_breakage"),
                ScrapReasonRow(quantity=1.0, reason="tool_breakage"),
                ScrapReasonRow(quantity=1.0, reason="material_defect"),
            ]
        )
        use_case = _use_case(repo)
        result = await use_case.scrap_by_reason(_filter(machine_id=7))

        assert repo.last_scope is not None
        assert repo.last_scope.machine_id == 7
        assert [row.reason for row in result.rows] == ["tool_breakage", "material_defect"]
        assert result.rows[0].quantity == 3.0
        assert result.rows[0].share.value == 0.75
        assert result.rows[1].quantity == 1.0
        assert result.rows[1].share.value == 0.25


class TestRejectedPerSupplier:
    async def test_empty_repository_yields_empty_rows(self) -> None:
        use_case = _use_case(FakeKpiRepository())
        result = await use_case.rejected_per_supplier(_filter())
        assert result.rows == []

    async def test_wires_repository_rows_through_kpi_rules(self) -> None:
        repo = FakeKpiRepository(
            supplier_deliveries=[
                SupplierDeliveryRow(
                    supplier_id=1,
                    supplier_name="Acme",
                    quantity=9.0,
                    quantity_rejected=1.0,
                    quantity_rejected_lost=1.0,
                ),
                SupplierDeliveryRow(
                    supplier_id=2,
                    supplier_name="Beta",
                    quantity=0.0,
                    quantity_rejected=0.0,
                    quantity_rejected_lost=0.0,
                ),
            ]
        )
        use_case = _use_case(repo)
        result = await use_case.rejected_per_supplier(_filter(project_id=5))

        assert repo.last_scope is not None
        assert repo.last_scope.project_id == 5
        by_id = {row.supplier_id: row for row in result.rows}
        assert by_id[1].delivered == 9.0
        assert by_id[1].rejected == 1.0
        assert by_id[1].rejected_ratio.value == 0.1
        assert by_id[1].rejected_lost == 1.0
        # A supplier with nothing received at all still surfaces, with a
        # None ratio rather than being dropped.
        assert by_id[2].rejected_ratio.value is None
