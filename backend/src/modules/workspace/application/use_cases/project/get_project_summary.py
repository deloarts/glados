"""
Read-side use case for a project's order cost and demand-status rollup,
shown on the project detail page.
"""

from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.workspace.domain.errors import ProjectNotFoundError
from src.modules.workspace.ports.outbound.project_work_port import IProjectWork
from src.modules.workspace.ports.outbound.project_work_port import ProjectSummaryRow
from src.modules.workspace.ports.outbound.repositories.project_repository import IProjectRepository


class GetProjectSummary:
    def __init__(self, project_repo: IProjectRepository, work: IProjectWork) -> None:
        self._projects = project_repo
        self._work = work

    async def execute(self, project_id: int) -> ProjectSummaryRow:
        found_or_raise(
            await self._projects.get_by_id(project_id),
            ProjectNotFoundError,
            f"Project #{project_id} not found.",
        )
        return await self._work.get_summary(project_id)
