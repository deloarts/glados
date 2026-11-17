"""
Creates a bought or made item demand for one catalogue item in one project.
The item must be one new work may name and the project must be active; the
project is locked in shared mode before it is checked, so a concurrent
delete of the project waits for this creation and then counts it
(IProjectQueries.lock_for_share). Without a desired delivery date in the
command the demand takes the project's required delivery date for its
family. The new demand is registered with the lifecycle reconciler, which
derives its status, and its creation event commits with it.

A family's subclass binds `_spec` and `_demand_rules` and supplies what
differs as hooks: the lookup and checks of its catalogue item, the demand
entity it builds and its creation event.
"""

from abc import abstractmethod
from typing import Generic
from typing import Protocol
from typing import TypeVar

from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases._demand_family.spec import CD
from src.modules.fulfillment.application.use_cases._demand_family.spec import CatalogueDemandRules
from src.modules.fulfillment.application.use_cases._demand_family.spec import DemandFamilySpec
from src.modules.fulfillment.application.use_cases._demand_family.spec import DemandRepo
from src.modules.fulfillment.application.use_cases._demand_family.spec import R
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.quantities import assert_whole_pieces
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.domain.entities.project import Project
from src.modules.workspace.domain.errors import ProjectNotFoundError
from src.modules.workspace.domain.policies.project_activity import assert_project_active
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries
from src.shared_kernel.domain.events.base import DomainEvent
from src.shared_kernel.domain.services.clock import now_utc


class CatalogueItem(Protocol):
    @property
    def article_name(self) -> str: ...


class CreateCommand(Protocol):
    @property
    def project_id(self) -> int: ...

    @property
    def quantity(self) -> float: ...


IT = TypeVar("IT", bound=CatalogueItem)
IT_co = TypeVar("IT_co", bound=CatalogueItem, covariant=True)
C = TypeVar("C", bound=CreateCommand)


class CatalogueItemRepo(Protocol[IT_co]):
    async def get_by_id(self, id: int, /) -> IT_co | None: ...


class CreateDemand(Generic[CD, IT, C, R]):
    _spec: DemandFamilySpec[CD, R]
    _demand_rules: CatalogueDemandRules[CD]

    def __init__(
        self,
        demand_repo: DemandRepo[CD],
        item_repo: CatalogueItemRepo[IT],
        project_repo: IProjectQueries,
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
    ) -> None:
        self._demands = demand_repo
        self._items = item_repo
        self._projects = project_repo
        self._bus = event_bus
        self._uow = uow
        self._reconciler = reconciler

    async def execute(self, actor: User, cmd: C) -> R:
        spec = self._spec
        self._demand_rules.assert_can_create(actor)
        self._demand_rules.assert_valid_quantity(cmd.quantity)
        item = await self._demandable_item(cmd)

        await self._projects.lock_for_share([cmd.project_id])
        project = found_or_raise(
            await self._projects.get_by_id(cmd.project_id),
            ProjectNotFoundError,
            f"Project #{cmd.project_id} not found.",
        )
        assert_project_active(project)

        demand = self._new_demand(actor, cmd, item, project)
        assert_whole_pieces(demand.quantity, what="The demand quantity", unit=demand.unit)
        saved = await self._demands.save(demand)
        self._reconciler.touch_demands(spec.aggregate, [saved.id], created=True)
        result = await self._reconciler.run(actor, now_utc())
        # The answer shows the demand as the run stored it.
        if result.changed_ids(spec.aggregate):
            saved = await self._demands.get_by_id(saved.id) or saved

        await self._bus.publish(self._created_event(saved))
        await self._uow.commit()

        log.info(
            f"Created demand for {item.article_name!r} "
            f"in project {project.project_number!r}, ID={saved.id}."
        )
        return spec.to_result(saved)

    @abstractmethod
    async def _demandable_item(self, cmd: C) -> IT:
        """The catalogue item the command names, once it is checked that new
        work may name it, together with the family's own checks of the
        command."""

    @abstractmethod
    def _new_demand(self, actor: User, cmd: C, item: IT, project: Project) -> CD:
        """The family's demand entity of the command, not yet saved."""

    @abstractmethod
    def _created_event(self, demand: CD) -> DomainEvent:
        """The family's creation event of the saved demand."""
