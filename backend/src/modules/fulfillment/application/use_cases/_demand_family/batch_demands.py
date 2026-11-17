"""
Validates and commits a batch of bought or made item demand rows that the
frontend parsed from an uploaded sheet. The importer only looks catalogue
items up; how a row finds its item is the family's row resolver, which both
use cases share, so the commit resolves every row again from scratch instead
of trusting what the client validated earlier.

The commit is all or nothing: a row that is not a clean match rolls the
whole batch back. The creation events are collected and published once
every row has resolved, before the single commit, so a row that fails late
never leaves an earlier row's event staged in a transaction that rolls
back. The new demands are registered with the lifecycle reconciler, which
derives their status.

A family's subclass binds `_spec`, `_demand_rules`, `_import_type`,
`_result` and `_log_kind`, builds its row resolver and supplies the demand
entity of a row and its creation event as hooks.
"""

from abc import abstractmethod
from collections.abc import Callable
from typing import Any
from typing import Generic
from typing import Protocol
from typing import TypeVar

from src.modules.catalogue.application.facade.data_import_limits import assert_import_row_limit
from src.modules.catalogue.domain.value_objects.data_import_type import DataImportType
from src.modules.fulfillment.application.services.batch_demand_import import LockedProjects
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases._demand_family.spec import CD
from src.modules.fulfillment.application.use_cases._demand_family.spec import CatalogueDemandRules
from src.modules.fulfillment.application.use_cases._demand_family.spec import DemandFamilySpec
from src.modules.fulfillment.application.use_cases._demand_family.spec import DemandRepo
from src.modules.fulfillment.domain.errors import BatchDemandRowInvalidError
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import DomainError
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.domain.entities.project import Project
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries
from src.shared_kernel.domain.events.base import DomainEvent
from src.shared_kernel.domain.services.clock import now_utc

MI_co = TypeVar("MI_co", covariant=True)


class BatchRow(Protocol):
    @property
    def row_index(self) -> int: ...


class RowResolution(Protocol[MI_co]):
    """What a family's row resolver reports for one row."""

    @property
    def row_status(self) -> str: ...

    @property
    def errors(self) -> list[str]: ...

    @property
    def matched_item(self) -> MI_co | None: ...

    @property
    def resolved_project_id(self) -> int | None: ...


Row = TypeVar("Row", bound=BatchRow)
Row_contra = TypeVar("Row_contra", bound=BatchRow, contravariant=True)
MI = TypeVar("MI")
RR = TypeVar("RR", bound=RowResolution[object])
RR_co = TypeVar("RR_co", bound=RowResolution[object], covariant=True)
VR = TypeVar("VR")
CR = TypeVar("CR")


class RowResolver(Protocol[Row_contra, RR_co]):
    async def resolve(self, row: Row_contra, /) -> RR_co: ...


class ValidateBatchDemands(Generic[CD, Row, RR, VR]):
    """`_result` builds the family's validation result from the row results
    and whether all of them matched."""

    _demand_rules: CatalogueDemandRules[CD]
    _import_type: DataImportType
    _result: Callable[..., VR]

    def __init__(
        self,
        resolver: RowResolver[Row, RR],
        *,
        settings_repo: IFulfillmentSettingsRepository | None = None,
    ) -> None:
        self._resolver = resolver
        self._settings = settings_repo

    async def execute(self, actor: User, rows: list[Row]) -> VR:
        self._demand_rules.assert_can_create(actor)
        await assert_import_row_limit(self._settings, self._import_type, len(rows))

        results = [await self._resolver.resolve(row) for row in rows]
        all_valid = all(r.row_status == "matched" for r in results)
        return self._result(results=results, all_valid=all_valid)


class CommitBatchDemands(Generic[CD, Row, MI, CR]):
    """`_result` builds the family's commit result from the created demand
    ids, and `_log_kind` names the import in the log line."""

    _spec: DemandFamilySpec[CD, Any]
    _demand_rules: CatalogueDemandRules[CD]
    _import_type: DataImportType
    _result: Callable[..., CR]
    _log_kind: str

    def __init__(
        self,
        demand_repo: DemandRepo[CD],
        project_repo: IProjectQueries,
        resolver: RowResolver[Row, RowResolution[MI]],
        uow: IUnitOfWork,
        *,
        event_bus: IEventBus,
        reconciler: LifecycleReconciler,
        settings_repo: IFulfillmentSettingsRepository | None = None,
    ) -> None:
        self._demands = demand_repo
        self._projects = project_repo
        self._resolver = resolver
        self._uow = uow
        self._bus = event_bus
        self._reconciler = reconciler
        self._settings = settings_repo

    async def execute(self, actor: User, rows: list[Row]) -> CR:
        self._demand_rules.assert_can_create(actor)
        await assert_import_row_limit(self._settings, self._import_type, len(rows))

        created_demand_ids: list[int] = []
        pending_events: list[DomainEvent] = []
        locked_projects = LockedProjects(self._projects)
        try:
            for row in rows:
                saved = await self._demands.save(
                    await self._row_demand(actor, row, locked_projects)
                )
                created_demand_ids.append(saved.id)
                pending_events.append(self._created_event(saved))
        except Exception:
            await self._uow.rollback()
            raise

        self._reconciler.touch_demands(self._spec.aggregate, created_demand_ids, created=True)
        await self._reconciler.run(actor, now_utc())

        for event in pending_events:
            await self._bus.publish(event)

        await self._uow.commit()
        log.info(f"Committed a {self._log_kind}: {len(created_demand_ids)} demands.")
        return self._result(created_demand_ids=created_demand_ids)

    async def _row_demand(self, actor: User, row: Row, locked_projects: LockedProjects) -> CD:
        """The demand of one row, resolved again from the current catalogue.
        Any row that is not a clean match blocks the whole batch, since the
        importer only ever creates demands for items that already exist."""
        result = await self._resolver.resolve(row)
        if (
            result.row_status != "matched"
            or result.matched_item is None
            or result.resolved_project_id is None
        ):
            reasons = "; ".join(result.errors) or "it no longer matches an item and a project"
            raise BatchDemandRowInvalidError(
                f"Row {row.row_index} cannot be imported any more: {reasons}"
            )
        try:
            project = await locked_projects.get(result.resolved_project_id)
        except DomainError as exc:
            # The same refusal with the same status, naming the row.
            exc.args = (f"Row {row.row_index}: {exc}",)
            raise
        return self._new_demand(
            actor, row, result.matched_item, result.resolved_project_id, project
        )

    @abstractmethod
    def _new_demand(self, actor: User, row: Row, item: MI, project_id: int, project: Project) -> CD:
        """The family's demand entity of the row, not yet saved."""

    @abstractmethod
    def _created_event(self, demand: CD) -> DomainEvent:
        """The family's creation event of the saved demand."""
