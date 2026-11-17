"""
PAT surface, read-only project access.
"""

from typing import Annotated

from fastapi import Depends
from fastapi import Query
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_user_pat
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.user import User
from src.modules.workspace.adapters.inbound.api.deps.products import get_project_by_number_use_case
from src.modules.workspace.adapters.inbound.api.deps.products import get_project_use_case
from src.modules.workspace.adapters.inbound.api.deps.products import get_projects_use_case
from src.modules.workspace.adapters.inbound.api.schemas.project_schema import ProjectFilterParams
from src.modules.workspace.adapters.inbound.api.schemas.project_schema import ProjectResponse
from src.modules.workspace.application.use_cases.project.get_project import GetProject
from src.modules.workspace.application.use_cases.project.get_project import GetProjectByNumber
from src.modules.workspace.application.use_cases.project.get_project import GetProjects

router = APIRouter()


@router.get("/", response_model=PageResponse[ProjectResponse])
async def read_projects(
    # Query-parameter model, not `Depends()`: see the note on
    # DemandItemFilterParams for why (list fields, e.g. `ids`).
    params: Annotated[ProjectFilterParams, Query()],
    _: User = Depends(get_current_user_pat),
    use_case: GetProjects = Depends(get_projects_use_case),
) -> PageResponse[ProjectResponse]:
    result = await use_case.execute(params.to_dto())
    return PageResponse.from_result(result, params, item_model=ProjectResponse)


@router.get("/{project_id}", response_model=ProjectResponse)
async def read_project_by_id(
    project_id: int,
    _: User = Depends(get_current_user_pat),
    use_case: GetProject = Depends(get_project_use_case),
) -> ProjectResponse:
    result = await use_case.execute(project_id=project_id)
    return ProjectResponse.model_validate(result.model_dump())


@router.get("/number/{project_number}", response_model=ProjectResponse)
async def read_project_by_number(
    project_number: str,
    _: User = Depends(get_current_user_pat),
    use_case: GetProjectByNumber = Depends(get_project_by_number_use_case),
) -> ProjectResponse:
    result = await use_case.execute(number=project_number)
    return ProjectResponse.model_validate(result.model_dump())
