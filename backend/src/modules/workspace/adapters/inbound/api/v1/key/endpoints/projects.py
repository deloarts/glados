"""
API key surface, read-only project access for hardware/machine clients.
Auth is verified at the router level via the API key dependency.
"""

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.workspace.adapters.inbound.api.deps.products import get_project_by_number_use_case
from src.modules.workspace.adapters.inbound.api.deps.products import get_project_use_case
from src.modules.workspace.adapters.inbound.api.schemas.project_schema import ProjectResponse
from src.modules.workspace.application.use_cases.project.get_project import GetProject
from src.modules.workspace.application.use_cases.project.get_project import GetProjectByNumber

router = APIRouter()


@router.get("/{project_id}", response_model=ProjectResponse)
async def read_project_by_id(
    project_id: int,
    use_case: GetProject = Depends(get_project_use_case),
) -> ProjectResponse:
    result = await use_case.execute(project_id=project_id)
    return ProjectResponse.model_validate(result.model_dump())


@router.get("/number/{project_number}", response_model=ProjectResponse)
async def read_project_by_number(
    project_number: str,
    use_case: GetProjectByNumber = Depends(get_project_by_number_use_case),
) -> ProjectResponse:
    result = await use_case.execute(number=project_number)
    return ProjectResponse.model_validate(result.model_dump())
