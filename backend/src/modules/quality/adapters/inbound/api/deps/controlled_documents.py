"""Builds the use case factories for one kind of controlled document. Saved
calculations, checklists and sequences wire the same use cases the same way
and differ only in their repository factory and use case classes, so each
kind's deps module calls this once and names the factories its endpoints
import. Create, update and release have their own builders, since a kind
whose use case needs more repositories writes that factory itself.

The factories are generic over the kind's repository type, inferred from its
repository factory, so each use case class is checked to take that
repository and the keywords its factory passes.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from typing import TypeVar

from fastapi import Depends

from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_fulfillment_settings_repo,
)
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
from src.modules.platform.adapters.inbound.api.deps.database import get_transactional_event_bus
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_product_repo
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_project_repo
from src.modules.workspace.ports.outbound.workspace_queries import IProductQueries
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries

RepoT = TypeVar("RepoT")
_RepoT_contra = TypeVar("_RepoT_contra", contravariant=True)

# A use case factory as FastAPI's `Depends()` takes it. FastAPI never reads
# its return annotation, so the factories declare the use case as `object`.
UseCaseFactory = Callable[..., object]


class _ReadUseCase(Protocol[_RepoT_contra]):
    def __call__(self, repo: _RepoT_contra, /) -> object: ...


class _UowUseCase(Protocol[_RepoT_contra]):
    def __call__(self, repo: _RepoT_contra, /, *, uow: IUnitOfWork) -> object: ...


class _EventUseCase(Protocol[_RepoT_contra]):
    def __call__(
        self, repo: _RepoT_contra, /, *, event_bus: IEventBus, uow: IUnitOfWork
    ) -> object: ...


class _ReviseUseCase(Protocol[_RepoT_contra]):
    def __call__(
        self,
        repo: _RepoT_contra,
        /,
        *,
        admin_settings_repo: IFulfillmentSettingsRepository,
        event_bus: IEventBus,
        uow: IUnitOfWork,
    ) -> object: ...


class _CreateUseCase(Protocol[_RepoT_contra]):
    def __call__(
        self,
        repo: _RepoT_contra,
        /,
        *,
        project_repo: IProjectQueries,
        product_repo: IProductQueries,
        admin_settings_repo: IFulfillmentSettingsRepository,
        uow: IUnitOfWork,
    ) -> object: ...


class _UpdateUseCase(Protocol[_RepoT_contra]):
    def __call__(
        self,
        repo: _RepoT_contra,
        /,
        *,
        project_repo: IProjectQueries,
        product_repo: IProductQueries,
        uow: IUnitOfWork,
    ) -> object: ...


@dataclass(frozen=True)
class ControlledDocumentUseCaseDeps:
    """The `Depends()` factories one kind's router reads."""

    get_many: UseCaseFactory
    get_one: UseCaseFactory
    get_revisions: UseCaseFactory
    get_by_public_id: UseCaseFactory
    revise: UseCaseFactory
    mark_invalid: UseCaseFactory
    delete: UseCaseFactory
    lock: UseCaseFactory
    unlock: UseCaseFactory


def build_controlled_document_deps(
    repo_dep: Callable[..., RepoT],
    *,
    get_many_cls: _ReadUseCase[RepoT],
    get_one_cls: _ReadUseCase[RepoT],
    get_revisions_cls: _ReadUseCase[RepoT],
    get_by_public_id_cls: _ReadUseCase[RepoT],
    revise_cls: _ReviseUseCase[RepoT],
    mark_invalid_cls: _EventUseCase[RepoT],
    delete_cls: _UowUseCase[RepoT],
    lock_cls: _EventUseCase[RepoT],
    unlock_cls: _EventUseCase[RepoT],
) -> ControlledDocumentUseCaseDeps:
    """Each use case class takes the kind's repository as its first
    positional argument, since its keyword names the kind."""

    def get_many(repo: RepoT = Depends(repo_dep)) -> object:
        return get_many_cls(repo)

    def get_one(repo: RepoT = Depends(repo_dep)) -> object:
        return get_one_cls(repo)

    def get_revisions(repo: RepoT = Depends(repo_dep)) -> object:
        return get_revisions_cls(repo)

    def get_by_public_id(repo: RepoT = Depends(repo_dep)) -> object:
        return get_by_public_id_cls(repo)

    def revise(
        repo: RepoT = Depends(repo_dep),
        admin_settings_repo: IFulfillmentSettingsRepository = Depends(
            get_fulfillment_settings_repo
        ),
        event_bus: IEventBus = Depends(get_transactional_event_bus),
        uow: IUnitOfWork = Depends(get_unit_of_work),
    ) -> object:
        return revise_cls(
            repo, admin_settings_repo=admin_settings_repo, event_bus=event_bus, uow=uow
        )

    def mark_invalid(
        repo: RepoT = Depends(repo_dep),
        event_bus: IEventBus = Depends(get_transactional_event_bus),
        uow: IUnitOfWork = Depends(get_unit_of_work),
    ) -> object:
        return mark_invalid_cls(repo, event_bus=event_bus, uow=uow)

    def delete(
        repo: RepoT = Depends(repo_dep),
        uow: IUnitOfWork = Depends(get_unit_of_work),
    ) -> object:
        return delete_cls(repo, uow=uow)

    def lock(
        repo: RepoT = Depends(repo_dep),
        event_bus: IEventBus = Depends(get_transactional_event_bus),
        uow: IUnitOfWork = Depends(get_unit_of_work),
    ) -> object:
        return lock_cls(repo, event_bus=event_bus, uow=uow)

    def unlock(
        repo: RepoT = Depends(repo_dep),
        event_bus: IEventBus = Depends(get_transactional_event_bus),
        uow: IUnitOfWork = Depends(get_unit_of_work),
    ) -> object:
        return unlock_cls(repo, event_bus=event_bus, uow=uow)

    return ControlledDocumentUseCaseDeps(
        get_many=get_many,
        get_one=get_one,
        get_revisions=get_revisions,
        get_by_public_id=get_by_public_id,
        revise=revise,
        mark_invalid=mark_invalid,
        delete=delete,
        lock=lock,
        unlock=unlock,
    )


def build_create_dep(
    repo_dep: Callable[..., RepoT], create_cls: _CreateUseCase[RepoT]
) -> UseCaseFactory:
    """The create factory of a kind whose create needs no repository beyond
    the projects, products and admin settings."""

    def create(
        repo: RepoT = Depends(repo_dep),
        project_repo: IProjectQueries = Depends(get_project_repo),
        product_repo: IProductQueries = Depends(get_product_repo),
        admin_settings_repo: IFulfillmentSettingsRepository = Depends(
            get_fulfillment_settings_repo
        ),
        uow: IUnitOfWork = Depends(get_unit_of_work),
    ) -> object:
        return create_cls(
            repo,
            project_repo=project_repo,
            product_repo=product_repo,
            admin_settings_repo=admin_settings_repo,
            uow=uow,
        )

    return create


def build_update_dep(
    repo_dep: Callable[..., RepoT], update_cls: _UpdateUseCase[RepoT]
) -> UseCaseFactory:
    """The update factory of a kind whose update needs no repository beyond
    the projects and products."""

    def update(
        repo: RepoT = Depends(repo_dep),
        project_repo: IProjectQueries = Depends(get_project_repo),
        product_repo: IProductQueries = Depends(get_product_repo),
        uow: IUnitOfWork = Depends(get_unit_of_work),
    ) -> object:
        return update_cls(repo, project_repo=project_repo, product_repo=product_repo, uow=uow)

    return update


def build_release_dep(
    repo_dep: Callable[..., RepoT], release_cls: _UowUseCase[RepoT]
) -> UseCaseFactory:
    """The release factory of a kind whose release checks nothing beyond the
    document itself."""

    def release(
        repo: RepoT = Depends(repo_dep),
        uow: IUnitOfWork = Depends(get_unit_of_work),
    ) -> object:
        return release_cls(repo, uow=uow)

    return release
