"""Fills the `actions` of project results, the status moves the reading user
may make on a project right now, and the live work counts a client shows on
the moves that work blocks. The actions come from the project's intent table
(src/modules/workspace/domain/services/lifecycle/project.py), the table the project use cases
check before they act, and the live work from the project work port.
"""

from collections.abc import Sequence
from dataclasses import asdict

from src.modules.platform.domain.entities.user import User
from src.modules.workspace.application.dto.project_dto import ProjectLiveWorkResult
from src.modules.workspace.application.dto.project_dto import ProjectResult
from src.modules.workspace.domain.services.lifecycle.project import PROJECT_INTENTS
from src.modules.workspace.domain.value_objects.project_live_work import ProjectLiveWork
from src.modules.workspace.ports.outbound.project_work_port import IProjectWork


class ProjectActions:
    def __init__(self, work: IProjectWork) -> None:
        self._work = work

    async def projects(self, results: Sequence[ProjectResult], actor: User) -> None:
        """Fills the actions and the live work counts, which a client shows
        on the moves the live work blocks."""
        if not results:
            return
        live_work = await self._work.get_live_work_by_ids([r.id for r in results])
        for project in results:
            work = live_work.get(project.id, ProjectLiveWork())
            project.live_work = ProjectLiveWorkResult(**asdict(work))
            project.actions = [
                action.value for action in PROJECT_INTENTS.allowed_actions(project, work, actor)
            ]
