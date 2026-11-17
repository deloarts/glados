"""
Repository interface for the MachineDowntime aggregate.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from typing import runtime_checkable

from src.modules.fulfillment.domain.entities.machine_downtime import MachineDowntime


@dataclass
class MachineDowntimeFilterDto:
    skip: int | None = None
    limit: int | None = None
    machine_id: int | None = None
    reason: str | None = None
    open_only: bool = False
    started_from: datetime | None = None
    started_to: datetime | None = None
    order_by: str | None = None
    order_dir: str | None = None


@runtime_checkable
class IMachineDowntimeRepository(Protocol):
    async def get_by_id(self, id: int) -> MachineDowntime | None: ...
    async def get_for_update(self, id: int) -> MachineDowntime | None:
        """The downtime read fresh under its row lock, so two writers that
        check whether it already ended cannot both pass that check."""
        ...

    async def get_multi(
        self, filters: MachineDowntimeFilterDto
    ) -> tuple[int, list[MachineDowntime]]:
        """Paginated, filtered list, mirroring IProductionMachineRepository.
        get_multi's naming, since a bare `list` as a method name breaks mypy's
        resolution of `list[...]` annotations elsewhere in this class."""
        ...

    async def get_open_by_machine_ids(
        self, machine_ids: list[int], *, started_by: datetime | None = None
    ) -> dict[int, MachineDowntime]:
        """One open downtime (ended_at IS NULL) per machine, batched in a
        single query for the machine list/detail read path. With
        `started_by`, only a downtime that began by then counts, so one
        reported ahead does not mark the machine down before it starts."""
        ...

    async def get_overlapping(
        self, machine_ids: list[int], start: datetime, end: datetime
    ) -> list[MachineDowntime]:
        """Every downtime row for the given machines whose window overlaps
        [start, end); an open downtime (ended_at IS NULL) counts as
        ongoing through `end`. Feeds the scheduling calendar builder
        (scheduling.apply_downtimes), not the availability KPI
        (see minutes_by_machine_in_period for that)."""
        ...

    async def minutes_by_machine_in_period(
        self, machine_ids: list[int], start: datetime, end: datetime
    ) -> dict[int, int]:
        """Downtime minutes per machine overlapping [start, end), for the
        availability KPI. An open downtime counts up to `end` (or `now`,
        whichever is earlier) as if it were still ongoing throughout the
        period. Machines with no overlapping downtime are absent from the
        result."""
        ...

    async def save(self, item: MachineDowntime) -> MachineDowntime: ...
    async def delete(self, item: MachineDowntime) -> None: ...
