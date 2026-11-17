"""
Repository interface for PdmReconciliationFinding, the rows one
ReconcilePdmVault run writes. The filter DTO lives here because ports may not
import application; pdm_dto.py holds its pydantic mirror.
"""

from dataclasses import dataclass
from typing import Protocol
from typing import runtime_checkable

from src.modules.external_data.domain.entities.pdm_reconciliation_finding import (
    PdmReconciliationFinding,
)


@dataclass
class PdmReconciliationFindingFilterDto:
    skip: int | None = None
    limit: int | None = None
    category: str | None = None
    kind: str | None = None
    search: str | None = None  # matches part_number, message
    part_number: str | None = None  # substring of part_number only
    message: str | None = None  # substring of message only


@runtime_checkable
class IPdmReconciliationFindingRepository(Protocol):
    async def add_many(self, findings: list[PdmReconciliationFinding]) -> None:
        """Inserts the findings. Does not commit; ReconcilePdmVault commits them
        with the run's finish()."""
        ...

    async def get_multi(
        self, run_id: int, filters: PdmReconciliationFindingFilterDto
    ) -> tuple[int, list[PdmReconciliationFinding]]:
        """Paged findings of one run, optionally filtered by category/kind,
        a search term matching part_number/message, and per-column
        part_number/message substrings, oldest first (the order categories
        were evaluated in)."""
        ...

    async def counts_for_run(self, run_id: int) -> dict[str, int]:
        """category -> sum(count) for `run_id`, for the admin dialog's count
        tiles. Summing `count` weights a grouped row by the files it stands
        for."""
        ...
