"""
What other readers read of Quality & documents: narrow query protocols over
its repositories, which the repositories satisfy as they are, and the filters
and rows they take and return. Writes go through Quality & documents' use
cases.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.quality.ports.outbound.repositories.production_kpi_repository import KpiScope
from src.modules.quality.ports.outbound.repositories.production_kpi_repository import (
    LateLotCandidateRow,
)

__all__ = ["IProductionKpiQueries", "KpiScope", "LateLotCandidateRow"]


@runtime_checkable
class IProductionKpiQueries(Protocol):
    async def get_late_lot_candidates(self, scope: KpiScope) -> list[LateLotCandidateRow]:
        """Every open lot matching scope with its latest order already
        resolved, the candidates of the late lots KPI."""
        ...
