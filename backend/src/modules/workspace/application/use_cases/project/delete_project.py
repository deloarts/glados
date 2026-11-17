"""
Soft-deletes a project (sets deleted=True, status=ARCHIVED). A project that
still has live work (lots, production orders, order lines or demands that are
not finished) is refused with the counts; that work is finished or canceled
through its own use cases first, so nothing is canceled here. The project
row is locked before its work is counted, and every use case that creates
work for a project locks it in shared mode before it checks the project, so
no work can appear between the count and the delete. The web route sends the
edit version the client read, so a project edited since answers 409.
"""

from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.edit_version import assert_edit_version
from src.modules.platform.domain.services.edit_version import bump_edit_version
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.application.dto.project_dto import ProjectResult
from src.modules.workspace.application.mappers.project_mapper import ProjectMapper
from src.modules.workspace.domain.errors import ProjectNotFoundError
from src.modules.workspace.domain.events.project_events import ProjectDeleted
from src.modules.workspace.domain.services.lifecycle.project import assert_project_deletable
from src.modules.workspace.domain.services.project_rules import ProjectRules
from src.modules.workspace.domain.value_objects.project_status import ProjectStatus
from src.modules.workspace.ports.outbound.project_work_port import IProjectWork
from src.modules.workspace.ports.outbound.repositories.project_repository import IProjectRepository
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class DeleteProject:
    def __init__(
        self,
        project_repo: IProjectRepository,
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        work: IProjectWork,
    ) -> None:
        self._projects = project_repo
        self._work = work
        self._bus = event_bus
        self._uow = uow

    async def execute(
        self, actor: User, project_id: int, expected_edit_version: int | None = None
    ) -> ProjectResult:
        # Permission check
        ProjectRules.assert_can_delete(actor)

        # Locked before the live work is counted, so a lot or demand created
        # concurrently either commits first and is counted or waits for this
        # delete and then finds the project gone (lock_for_share).
        await self._projects.lock_for_update(project_id)
        project = found_or_raise(
            await self._projects.get_by_id(project_id),
            ProjectNotFoundError,
            f"Project #{project_id} not found.",
        )
        assert_edit_version(project, expected_edit_version, what=f"Project #{project.id}")

        assert_project_deletable(project, await self._work.get_live_work(project_id))

        # Soft-delete the project itself. The archive transition is recorded in
        # the project's own changelog: it never goes through UpdateProject, so
        # nothing else would leave a trace of it in the project's history.
        project.deleted = True
        project.status = ProjectStatus.ARCHIVED
        project.changed = now_utc()
        project.changes = append_changelog(project.changes, actor.full_name, "Project deleted.")
        bump_edit_version(project)
        saved = await self._projects.save(project)

        # Staged in the same transaction as the write it describes
        # (see event_outbox.py): publish before commit, always.
        await self._bus.publish(
            ProjectDeleted(
                project_id=saved.id,
                project_number=saved.project_number,
                actor_id=actor.id,
            )
        )

        await self._uow.commit()

        log.info(f"Deleted project {saved.project_number!r} (ID={saved.id}).")

        return ProjectMapper.to_result(saved)
