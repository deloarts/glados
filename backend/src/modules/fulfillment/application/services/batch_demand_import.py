"""
The parts the bought and the made item batch demand importers share: value
normalisation for the exact lookups, the quantity check, project resolution,
the refusals a resolved row's demand would meet, the row status precedence,
the commit's per-project shared lock and the import's row limit. How a row's item is looked up, and
the demand it creates, stay with each importer.
"""

import math
from collections.abc import Callable
from typing import Literal

from src.modules.platform.application.services.import_text import norm
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.services.quantities import counts_whole_units
from src.modules.platform.domain.services.quantities import is_whole_quantity
from src.modules.platform.domain.services.quantities import storage_refusal
from src.modules.workspace.domain.entities.project import Project
from src.modules.workspace.domain.errors import ProjectInactiveError
from src.modules.workspace.domain.errors import ProjectNotFoundError
from src.modules.workspace.domain.policies.project_activity import assert_project_active
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries
from src.modules.workspace.ports.outbound.workspace_queries import ProjectFilterDto

ItemLookupStatus = Literal["matched", "ambiguous", "not_found"]
RowStatus = Literal["matched", "not_found", "ambiguous", "unresolved_reference", "invalid"]


def quantity_error(quantity: float | None, unit: str | None = None) -> str | None:
    """Why a row's quantity is refused, if it is. The import rows are
    permissive at the schema, so NaN and infinity reach this check and are
    refused per row, as is one the quantity columns cannot store
    (storage_refusal). A quantity in pieces, or in a `unit` that counts whole
    things, must be a whole number; without `unit` it counts pieces."""
    if quantity is not None and not math.isfinite(quantity):
        return "Quantity must be a finite number."
    if quantity is None or quantity <= 0:
        return "Quantity must be greater than 0."
    refusal = storage_refusal(quantity)
    if refusal is not None:
        return refusal
    counts = unit is None or counts_whole_units(unit)
    if counts and not is_whole_quantity(quantity):
        return "Quantity must be a whole number."
    return None


async def resolve_project(
    projects: IProjectQueries, project_number: str | None
) -> tuple[Project | None, str | None]:
    """The project whose number matches exactly once normalised, or the
    error naming the number that matched none."""
    _, candidates = await projects.get_multi(ProjectFilterDto(project_number=project_number))
    exact = next((p for p in candidates if norm(p.project_number) == norm(project_number)), None)
    if exact:
        return exact, None
    return None, f"Project {project_number!r} not found."


def new_demand_refusals[I](
    project: Project | None,
    item: I | None,
    *,
    assert_item_demandable: Callable[[I], None],
    item_error: type[Exception],
) -> list[str]:
    """Why a demand for the resolved project and item would be refused: the
    project is not active, or the item is one new work may not name."""
    refusals: list[str] = []
    try:
        if project is not None:
            assert_project_active(project)
    except ProjectInactiveError as exc:
        refusals.append(str(exc))
    try:
        if item is not None:
            assert_item_demandable(item)
    except item_error as exc:
        refusals.append(str(exc))
    return refusals


def decide_row_status(
    project_error: str | None,
    item_status: ItemLookupStatus,
    item_errors: list[str],
    refusals: list[str],
) -> tuple[RowStatus, list[str]]:
    """The status and errors of a well-formed row: unresolved_reference
    before ambiguous before not_found, then invalid for a resolved row whose
    demand would be refused, otherwise matched."""
    if project_error:
        return "unresolved_reference", [project_error, *item_errors]
    if item_status != "matched":
        return item_status, [*item_errors, *refusals]
    if refusals:
        return "invalid", refusals
    return "matched", []


class LockedProjects:
    """The projects a batch commit writes demands for, each locked in shared
    mode and checked again once, since many rows of a sheet share one. The
    shared lock makes a concurrent delete of the project wait for the import
    and then count its demands (IProjectQueries)."""

    def __init__(self, projects: IProjectQueries) -> None:
        self._projects = projects
        self._cache: dict[int, Project] = {}

    async def get(self, project_id: int) -> Project:
        if project_id not in self._cache:
            await self._projects.lock_for_share([project_id])
            project = found_or_raise(
                await self._projects.get_by_id(project_id),
                ProjectNotFoundError,
                f"Project #{project_id} not found.",
            )
            assert_project_active(project)
            self._cache[project_id] = project
        return self._cache[project_id]
