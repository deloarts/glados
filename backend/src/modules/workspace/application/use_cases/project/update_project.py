"""Updates a project's number, customer, product, description, owner, status, production time
budget, and required delivery dates, then records the change in the project's changelog. When
requested, also propagates a changed delivery date onto the project's non-terminal demands and
the lots already allocated against them.

A changed status is a status move of the project's intent table: it needs manage:projects, and
completing or archiving the project is refused while it has live work. The project row is locked
before that work is counted, and every use case that creates work for a project share-locks it
first, so no work appears between the count and the move. A client sends the edit version it
read; a project edited since answers 409, and every update moves the version.

The work belongs to Planning & fulfillment, so the live work count and the propagation go
through the project work ports (ports/outbound/project_work_port.py).
"""

from typing import Any

from src.modules.catalogue.api import ICatalogueSettingsRepository
from src.modules.catalogue.domain.errors import CustomerNotFoundError
from src.modules.catalogue.ports.outbound.catalogue_queries import ICustomerQueries
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.schedule_recompute_port import ScheduleRecompute
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.domain.entities.admin_settings.general import AdminGeneralSettings
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import UserNotFoundError
from src.modules.platform.domain.services.edit_version import assert_edit_version
from src.modules.platform.domain.services.edit_version import bump_edit_version
from src.modules.platform.domain.services.number_pattern import matches
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.application.dto.project_dto import ProjectResult
from src.modules.workspace.application.dto.project_dto import UpdateProjectCommand
from src.modules.workspace.application.mappers.project_mapper import ProjectMapper
from src.modules.workspace.domain.entities.project import Project
from src.modules.workspace.domain.errors import ProductNotFoundError
from src.modules.workspace.domain.errors import ProjectAlreadyExistsError
from src.modules.workspace.domain.errors import ProjectNotFoundError
from src.modules.workspace.domain.errors import ProjectNumberPatternError
from src.modules.workspace.domain.errors import ProjectProductRequiredError
from src.modules.workspace.domain.events.project_events import ProjectUpdated
from src.modules.workspace.domain.services.lifecycle.project import assert_project_status_move
from src.modules.workspace.domain.services.project_rules import ProjectRules
from src.modules.workspace.ports.outbound.project_work_port import IProjectWork
from src.modules.workspace.ports.outbound.project_work_port import IProjectWorkPropagation
from src.modules.workspace.ports.outbound.project_work_port import ProjectWorkChange
from src.modules.workspace.ports.outbound.repositories.product_repository import IProductRepository
from src.modules.workspace.ports.outbound.repositories.project_repository import IProjectRepository
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.changelog_service import diff_changes
from src.shared_kernel.domain.services.clock import now_utc


class UpdateProject:
    def __init__(
        self,
        project_repo: IProjectRepository,
        user_repo: IUserRepository,
        product_repo: IProductRepository | None = None,
        customer_repo: ICustomerQueries | None = None,
        *,
        uow: IUnitOfWork,
        event_bus: IEventBus,
        settings_repo: ICatalogueSettingsRepository,
        work: IProjectWork,
        propagation: IProjectWorkPropagation,
        recompute_schedule: ScheduleRecompute | None = None,
    ) -> None:
        """The work port counts the project's live work for a status move;
        the propagation port carries a changed delivery date or time budget
        onto that work. The schedule walk runs after the commit when a time
        budget change moved a machine's queue."""
        self._work = work
        self._propagation = propagation
        self._recompute = recompute_schedule
        self._projects = project_repo
        self._users = user_repo
        self._products = product_repo
        self._customers = customer_repo
        self._uow = uow
        self._bus = event_bus
        self._settings = settings_repo

    async def execute(
        self, actor: User, project_id: int, cmd: UpdateProjectCommand
    ) -> ProjectResult:
        # The project row before any lot or demand row it propagates to, the
        # order every writer of a project and its work follows.
        await self._projects.lock_for_update(project_id)
        project = found_or_raise(
            await self._projects.get_by_id(project_id),
            ProjectNotFoundError,
            f"Project #{project_id} not found.",
        )

        ProjectRules.assert_can_update(actor, project)
        assert_edit_version(project, cmd.expected_edit_version, what=f"Project #{project.id}")
        await self._check_status_move(actor, project, cmd.status)

        general = await self._settings.get_general()
        effective_user_id = await self._validate_and_resolve_owner(actor, project, cmd, general)
        old_designated_user_id = project.designated_user_id

        old = self._snapshot(project)
        change = ProjectWorkChange(
            old_delivery_date_made=project.required_delivery_date_made,
            old_delivery_date_bought=project.required_delivery_date_bought,
            propagate_delivery_date_made=cmd.propagate_delivery_date_made,
            propagate_delivery_date_bought=cmd.propagate_delivery_date_bought,
            recompute_time_budgets=project.production_time_budget != cmd.production_time_budget,
        )
        new = self._apply_changes(project, cmd, effective_user_id)
        project.changed = now_utc()
        project.changes = append_changelog(project.changes, actor.full_name, diff_changes(old, new))
        bump_edit_version(project)

        saved = await self._projects.save(project)

        saved = await self._propagate_delivery_dates(actor, saved, change)
        # After the propagation's row locks: the time budget lock comes after
        # every lifecycle row a writer locks, so it never waits for a lot
        # while it holds the budgets another writer is waiting for.
        touched_machine_ids: set[int | None] = set()
        if change.recompute_time_budgets:
            touched_machine_ids = await self._propagation.recompute_time_budgets(saved.id)

        await self._bus.publish(
            ProjectUpdated(
                project_id=saved.id,
                project_number=saved.project_number,
                actor_id=actor.id,
                designated_user_id=saved.designated_user_id,
                old_designated_user_id=old_designated_user_id,
            )
        )
        # The project, the recomputed time budgets with the durations they
        # snapshot, the propagated dates and the event commit together.
        await self._uow.commit()
        if touched_machine_ids:
            await recompute_schedule_after_commit(
                self._recompute,
                after=f"updating project #{saved.id}; the update itself is committed.",
            )

        log.info(f"Updated project {saved.project_number!r} (ID={saved.id}).")

        return ProjectMapper.to_result(saved)

    async def _check_status_move(self, actor: User, project: Project, target: str | None) -> None:
        """Refuses a status move the actor may not make or the project's
        intent table does not allow now; a status left as it is passes."""
        if target is None or target == project.status:
            return
        ProjectRules.assert_can_move_status(actor)
        live_work = await self._work.get_live_work(project.id)
        assert_project_status_move(project, target, live_work, actor)

    async def _validate_and_resolve_owner(
        self,
        actor: User,
        project: Project,
        cmd: UpdateProjectCommand,
        general: AdminGeneralSettings,
    ) -> int:
        """Validates the update and returns the effective designated user."""
        # Only checked when the number changes, so tightening the pattern
        # does not block edits to projects numbered before.
        if cmd.project_number != project.project_number:
            if not matches(cmd.project_number, general.project_number_pattern):
                raise ProjectNumberPatternError(
                    f"Project number {cmd.project_number!r} does not match the "
                    f"required pattern ({general.project_number_pattern})."
                )

            existing = await self._projects.get_by_project_number(cmd.project_number)
            if existing and existing.id != project.id:
                raise ProjectAlreadyExistsError(
                    f"A project with number {cmd.project_number!r} already exists."
                )

        # Only removing a product is rejected, so a headless project created
        # while headless projects were allowed stays editable.
        if (
            not general.allow_headless_projects
            and cmd.product_id is None
            and project.product_id is not None
        ):
            raise ProjectProductRequiredError("A project must reference a product.")

        if cmd.customer_id is not None and (
            not self._customers or not await self._customers.get_by_id(cmd.customer_id)
        ):
            raise CustomerNotFoundError(f"Customer #{cmd.customer_id} does not exist.")

        if cmd.product_id is not None and (
            not self._products or not await self._products.get_by_id(cmd.product_id)
        ):
            raise ProductNotFoundError(f"Product #{cmd.product_id} does not exist.")

        if cmd.designated_user_id is None:
            # Omitted keeps the owner, so a forgotten field never transfers it.
            return project.designated_user_id

        ProjectRules.assert_can_assign_designated_user(actor, cmd.designated_user_id)
        if not await self._users.get_by_id(cmd.designated_user_id):
            raise UserNotFoundError(f"Designated user #{cmd.designated_user_id} does not exist.")
        return cmd.designated_user_id

    def _snapshot(self, project: Project) -> dict[str, Any]:
        """Snapshots the project for the changelog diff, which compares
        before and after rather than the command, since omitted fields mean
        unchanged."""
        return {
            "project_number": project.project_number,
            "customer_id": project.customer_id,
            "product_id": project.product_id,
            "description": project.description,
            "designated_user_id": project.designated_user_id,
            "status": project.status,
            "production_time_budget": project.production_time_budget,
            "required_delivery_date_made": project.required_delivery_date_made,
            "required_delivery_date_bought": project.required_delivery_date_bought,
        }

    def _apply_changes(
        self, project: Project, cmd: UpdateProjectCommand, effective_user_id: int
    ) -> dict[str, Any]:
        """Applies the changes in place and returns the new snapshot."""
        project.project_number = cmd.project_number
        project.customer_id = cmd.customer_id
        project.product_id = cmd.product_id
        if cmd.description is not None:
            project.description = cmd.description
        project.designated_user_id = effective_user_id
        if cmd.status is not None:
            project.status = cmd.status
        project.production_time_budget = cmd.production_time_budget
        # Full PUT: null clears a date.
        project.required_delivery_date_made = cmd.required_delivery_date_made
        project.required_delivery_date_bought = cmd.required_delivery_date_bought

        return {
            "project_number": project.project_number,
            "customer_id": project.customer_id,
            "product_id": project.product_id,
            "description": project.description,
            "designated_user_id": project.designated_user_id,
            "status": project.status,
            "production_time_budget": project.production_time_budget,
            "required_delivery_date_made": project.required_delivery_date_made,
            "required_delivery_date_bought": project.required_delivery_date_bought,
        }

    async def _propagate_delivery_dates(
        self, actor: User, saved: Project, change: ProjectWorkChange
    ) -> Project:
        """Locks and propagates through the propagation port, and summarizes
        the affected counts in the project's changelog, since the user never
        named those rows."""
        await self._propagation.lock(saved, change)
        propagation_notes = await self._propagation.propagate_delivery_dates(actor, saved, change)
        if propagation_notes:
            # "; " because the changelog line is itself comma-delimited.
            saved.changes = append_changelog(
                saved.changes, actor.full_name, "; ".join(propagation_notes)
            )
            saved = await self._projects.save(saved)

        return saved
