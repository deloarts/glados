"""
What the project use cases need from the work planned on a project: its lots,
production orders, order lines, demands and quote requests. A project knows
nothing about that work itself, so Workspace owns these two ports and Planning
& fulfillment implements them; the composition root wires the implementations
into the project use cases.
"""

from dataclasses import dataclass
from datetime import date
from typing import Protocol
from typing import TypedDict
from typing import runtime_checkable

from src.modules.platform.domain.entities.user import User
from src.modules.workspace.domain.entities.project import Project
from src.modules.workspace.domain.value_objects.project_live_work import ProjectLiveWork


class ProjectCostBySupplierRow(TypedDict):
    supplier_id: int
    supplier_name: str
    ordered_cost: int
    delivered_cost: int


class ProjectSummaryRow(TypedDict):
    """The order cost and demand-status rollup of a project or a product,
    mirrored by the web schema's ProjectSummaryResponse
    (adapters/inbound/api/schemas/project_schema.py); kept here rather than
    imported from there since application/ports code must not depend on the
    adapters layer."""

    total_ordered_cost: int
    total_delivered_cost: int
    order_count: int
    cost_by_supplier: list[ProjectCostBySupplierRow]
    demand_counts: dict[str, int]


@runtime_checkable
class IProjectWork(Protocol):
    async def get_live_work(self, project_id: int) -> ProjectLiveWork:
        """Counts the project's unfinished lots, production orders, order
        lines, demands of the three families and open quote requests."""
        ...

    async def get_live_work_by_ids(self, project_ids: list[int]) -> dict[int, ProjectLiveWork]:
        """get_live_work for every listed project at once, keyed by id."""
        ...

    async def get_summary(self, project_id: int) -> ProjectSummaryRow:
        """The project's order cost and demand-status rollup."""
        ...


@runtime_checkable
class IProductWork(Protocol):
    async def get_product_summary(self, product_id: int) -> ProjectSummaryRow:
        """The order cost and demand-status rollup over all projects built
        on the product."""
        ...


@dataclass(frozen=True)
class ProjectWorkChange:
    """What a project update asks of its work. The old dates are the ones
    the project had before the update; a date propagates only when its flag
    is set and the project's new date differs from the old one."""

    old_delivery_date_made: date | None
    old_delivery_date_bought: date | None
    propagate_delivery_date_made: bool
    propagate_delivery_date_bought: bool
    recompute_time_budgets: bool


@runtime_checkable
class IProjectWorkPropagation(Protocol):
    async def lock(self, project: Project, change: ProjectWorkChange) -> None:
        """Locks every lot, production order and demand the change may
        write in one acquisition, so they are taken in the one lock order.
        The project row is locked before this by the caller."""
        ...

    async def propagate_delivery_dates(
        self, actor: User, project: Project, change: ProjectWorkChange
    ) -> list[str]:
        """Sets the project's changed delivery dates on its open demands and
        the open lots allocated to them, and returns one changelog note per
        propagated date for the project."""
        ...

    async def recompute_time_budgets(self, project_id: int) -> set[int | None]:
        """Recomputes the time budgets of the project's lots and the
        durations of their queued and paused production orders, and returns
        the machines whose schedule changed. Called after the propagation,
        since the time budget lock comes after every lifecycle row lock."""
        ...
