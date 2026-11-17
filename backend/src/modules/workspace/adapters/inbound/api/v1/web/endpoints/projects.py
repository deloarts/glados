"""
Web surface project endpoints. Thin, parse HTTP, call use case, return response.
"""

from typing import Annotated

from fastapi import Depends
from fastapi import Query
from fastapi import status
from fastapi.routing import APIRouter
from pydantic import Field

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.user import User
from src.modules.workspace.adapters.inbound.api.deps.products import get_create_project_use_case
from src.modules.workspace.adapters.inbound.api.deps.products import get_delete_project_use_case
from src.modules.workspace.adapters.inbound.api.deps.products import get_my_projects_use_case
from src.modules.workspace.adapters.inbound.api.deps.products import get_project_actions
from src.modules.workspace.adapters.inbound.api.deps.products import get_project_by_number_use_case
from src.modules.workspace.adapters.inbound.api.deps.products import get_project_summary_use_case
from src.modules.workspace.adapters.inbound.api.deps.products import get_project_use_case
from src.modules.workspace.adapters.inbound.api.deps.products import (
    get_projects_by_product_id_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.products import get_projects_use_case
from src.modules.workspace.adapters.inbound.api.deps.products import get_update_project_use_case
from src.modules.workspace.adapters.inbound.api.schemas.project_schema import ProjectCreateRequest
from src.modules.workspace.adapters.inbound.api.schemas.project_schema import ProjectFilterParams
from src.modules.workspace.adapters.inbound.api.schemas.project_schema import ProjectResponse
from src.modules.workspace.adapters.inbound.api.schemas.project_schema import ProjectSummaryResponse
from src.modules.workspace.adapters.inbound.api.schemas.project_schema import ProjectUpdateRequest
from src.modules.workspace.application.dto.project_dto import CreateProjectCommand
from src.modules.workspace.application.dto.project_dto import ProjectResult
from src.modules.workspace.application.dto.project_dto import UpdateProjectCommand
from src.modules.workspace.application.services.project_actions import ProjectActions
from src.modules.workspace.application.use_cases.project.create_project import CreateProject
from src.modules.workspace.application.use_cases.project.delete_project import DeleteProject
from src.modules.workspace.application.use_cases.project.get_project import GetMyProjects
from src.modules.workspace.application.use_cases.project.get_project import GetProject
from src.modules.workspace.application.use_cases.project.get_project import GetProjectByNumber
from src.modules.workspace.application.use_cases.project.get_project import GetProjects
from src.modules.workspace.application.use_cases.project.get_project import GetProjectsByProductId
from src.modules.workspace.application.use_cases.project.get_project_summary import (
    GetProjectSummary,
)
from src.modules.workspace.application.use_cases.project.update_project import UpdateProject
from src.modules.workspace.ports.outbound.project_work_port import ProjectSummaryRow
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction

router = APIRouter()


class ProjectLiveWorkResponse(ResponseModel):
    """The project's unfinished work per kind, which blocks completing,
    archiving and deleting it."""

    lots: int
    production_orders: int
    order_lines: int
    bought_demands: int
    made_demands: int
    source_demands: int
    quote_requests: int


class ProjectWebResponse(ProjectResponse):
    """Web-only extension of ProjectResponse: the edit version a status move
    or edit sends back, the status moves and the delete the reading user may
    take now, and the live work that blocks the others. The SolidWorks
    add-in only reads projects, so these stay off the shared response class
    the PAT surface also returns, to avoid widening that frozen contract."""

    edit_version: int
    actions: list[LifecycleAction] = Field(default_factory=list)
    live_work: ProjectLiveWorkResponse | None = None


def _web(result: ProjectResult) -> ProjectWebResponse:
    return ProjectWebResponse.model_validate(result.model_dump())


# ── GET /projects/ ────────────────────────────────────────────────────


@router.get("/", response_model=PageResponse[ProjectWebResponse])
async def read_projects(
    # Query-parameter model, not `Depends()`: see the note on
    # DemandItemFilterParams for why (list fields, e.g. `ids`).
    params: Annotated[ProjectFilterParams, Query()],
    actor: User = Depends(get_current_active_user),
    use_case: GetProjects = Depends(get_projects_use_case),
    actions: ProjectActions = Depends(get_project_actions),
) -> PageResponse[ProjectWebResponse]:
    result = await use_case.execute(params.to_dto())
    await actions.projects(result.items, actor)
    return PageResponse.from_result(result, params, item_model=ProjectWebResponse)


# ── POST /projects/ ───────────────────────────────────────────────────


@router.post("/", response_model=ProjectWebResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateProject = Depends(get_create_project_use_case),
    actions: ProjectActions = Depends(get_project_actions),
) -> ProjectWebResponse:
    cmd = CreateProjectCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, cmd=cmd)
    await actions.projects([result], actor)
    return _web(result)


# ── GET /projects/my ──────────────────────────────────────────────────


@router.get("/my", response_model=list[ProjectWebResponse])
async def read_my_projects(
    current_user: User = Depends(get_current_active_user),
    use_case: GetMyProjects = Depends(get_my_projects_use_case),
    actions: ProjectActions = Depends(get_project_actions),
) -> list[ProjectWebResponse]:
    """Returns projects where the current user is the designated user."""
    results = await use_case.execute(user_id=current_user.id)
    await actions.projects(results, current_user)
    return [_web(r) for r in results]


# ── GET /projects/{project_id}/summary ───────────────────────────────


@router.get("/{project_id}/summary", response_model=ProjectSummaryResponse)
async def get_project_summary(
    project_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetProjectSummary = Depends(get_project_summary_use_case),
) -> ProjectSummaryRow:
    return await use_case.execute(project_id)


# ── GET /projects/{project_id} ────────────────────────────────────────


@router.get("/{project_id}", response_model=ProjectWebResponse)
async def read_project_by_id(
    project_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: GetProject = Depends(get_project_use_case),
    actions: ProjectActions = Depends(get_project_actions),
) -> ProjectWebResponse:
    result = await use_case.execute(project_id=project_id)
    await actions.projects([result], actor)
    return _web(result)


@router.get("/{project_id}/changelog", response_model=list[str])
async def read_project_changelog(
    project_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetProject = Depends(get_project_use_case),
) -> list[str]:
    return (await use_case.execute(project_id=project_id)).changes


# ── GET /projects/number/{project_number} ────────────────────────────


@router.get("/number/{project_number}", response_model=ProjectWebResponse)
async def read_project_by_number(
    project_number: str,
    actor: User = Depends(get_current_active_user),
    use_case: GetProjectByNumber = Depends(get_project_by_number_use_case),
    actions: ProjectActions = Depends(get_project_actions),
) -> ProjectWebResponse:
    result = await use_case.execute(number=project_number)
    await actions.projects([result], actor)
    return _web(result)


# ── GET /projects/product/{product_id} ───────────────────────────────


@router.get("/product/{product_id}", response_model=list[ProjectWebResponse])
async def read_projects_by_product_id(
    product_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: GetProjectsByProductId = Depends(get_projects_by_product_id_use_case),
    actions: ProjectActions = Depends(get_project_actions),
) -> list[ProjectWebResponse]:
    results = await use_case.execute(product_id=product_id)
    await actions.projects(results, actor)
    return [_web(r) for r in results]


# ── PUT /projects/{project_id} ────────────────────────────────────────


@router.put("/{project_id}", response_model=ProjectWebResponse)
async def update_project(
    project_id: int,
    body: ProjectUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateProject = Depends(get_update_project_use_case),
    actions: ProjectActions = Depends(get_project_actions),
) -> ProjectWebResponse:
    cmd = UpdateProjectCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, project_id=project_id, cmd=cmd)
    await actions.projects([result], actor)
    return _web(result)


# ── DELETE /projects/{project_id} ────────────────────────────────────


@router.delete("/{project_id}", response_model=ProjectWebResponse)
async def delete_project(
    project_id: int,
    expected_edit_version: int = Query(
        description="The edit version read; a project that moved since answers 409."
    ),
    actor: User = Depends(get_current_active_user),
    use_case: DeleteProject = Depends(get_delete_project_use_case),
) -> ProjectWebResponse:
    result = await use_case.execute(
        actor=actor, project_id=project_id, expected_edit_version=expected_edit_version
    )
    return _web(result)
