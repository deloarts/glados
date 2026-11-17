"""
Read-side use cases for fetching one or more projects, by id, project number, product id, or
designated user, or as a paginated, filtered listing.
"""

from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.workspace.application.dto.project_dto import ProjectResult
from src.modules.workspace.application.mappers.project_mapper import ProjectMapper
from src.modules.workspace.domain.errors import ProjectNotFoundError
from src.modules.workspace.ports.outbound.repositories.project_repository import IProjectRepository
from src.modules.workspace.ports.outbound.workspace_queries import ProjectFilterDto


class PaginatedProjects:
    def __init__(self, total: int, items: list[ProjectResult]):
        self.total = total
        self.items = items


class GetProject:
    def __init__(self, project_repo: IProjectRepository) -> None:
        self._repo = project_repo

    async def execute(self, project_id: int) -> ProjectResult:
        project = found_or_raise(
            await self._repo.get_by_id(project_id),
            ProjectNotFoundError,
            f"Project #{project_id} not found.",
        )
        return ProjectMapper.to_result(project)


class GetProjectByNumber:
    def __init__(self, project_repo: IProjectRepository) -> None:
        self._repo = project_repo

    async def execute(self, number: str) -> ProjectResult:
        project = found_or_raise(
            await self._repo.get_by_project_number(number),
            ProjectNotFoundError,
            f"Project with number {number!r} not found.",
        )
        return ProjectMapper.to_result(project)


class GetProjectsByProductId:
    def __init__(self, project_repo: IProjectRepository) -> None:
        self._repo = project_repo

    async def execute(self, product_id: int) -> list[ProjectResult]:
        projects = await self._repo.get_by_product_id(product_id)
        return [ProjectMapper.to_result(p) for p in projects]


class GetMyProjects:
    def __init__(self, project_repo: IProjectRepository) -> None:
        self._repo = project_repo

    async def execute(self, user_id: int) -> list[ProjectResult]:
        projects = await self._repo.get_by_designated_user_id(user_id)
        return [ProjectMapper.to_result(p) for p in projects]


class GetProjects:
    def __init__(self, project_repo: IProjectRepository) -> None:
        self._repo = project_repo

    async def execute(self, filters: ProjectFilterDto) -> PaginatedProjects:
        total, projects = await self._repo.get_multi(filters)
        return PaginatedProjects(
            total=total,
            items=[ProjectMapper.to_result(p) for p in projects],
        )
