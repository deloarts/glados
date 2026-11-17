"""
Endpoints for PLC environments, mounted under /product-device-resources
next to the other lists the PLC engineer maintains. Every route needs a
login; editing and archiving check their permissions in the use cases.
"""

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query
from fastapi import status

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.domain.entities.user import User
from src.modules.workspace.adapters.inbound.api.deps.plc_environments import (
    get_create_plc_environment_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.plc_environments import (
    get_plc_environment_template_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.plc_environments import (
    get_plc_environments_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.plc_environments import (
    get_set_plc_environment_archived_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.plc_environments import (
    get_update_plc_environment_use_case,
)
from src.modules.workspace.adapters.inbound.api.schemas.plc_environment_schema import (
    PlcEnvironmentResponse,
)
from src.modules.workspace.adapters.inbound.api.schemas.plc_environment_schema import (
    PlcEnvironmentSaveRequest,
)
from src.modules.workspace.adapters.inbound.api.schemas.plc_environment_schema import (
    PlcEnvironmentSettingsSchema,
)
from src.modules.workspace.application.dto.plc_environment_dto import SavePlcEnvironmentCommand
from src.modules.workspace.application.use_cases.plc_environment.environments import (
    CreatePlcEnvironment,
)
from src.modules.workspace.application.use_cases.plc_environment.environments import (
    GetPlcEnvironments,
)
from src.modules.workspace.application.use_cases.plc_environment.environments import (
    GetPlcEnvironmentTemplate,
)
from src.modules.workspace.application.use_cases.plc_environment.environments import (
    SetPlcEnvironmentArchived,
)
from src.modules.workspace.application.use_cases.plc_environment.environments import (
    UpdatePlcEnvironment,
)

router = APIRouter()


@router.get("/plc-environments", response_model=list[PlcEnvironmentResponse])
async def read_plc_environments(
    include_archived: bool = Query(default=False),
    _: User = Depends(get_current_active_user),
    use_case: GetPlcEnvironments = Depends(get_plc_environments_use_case),
) -> list[PlcEnvironmentResponse]:
    results = await use_case.execute(include_archived)
    return [PlcEnvironmentResponse.model_validate(r.model_dump()) for r in results]


@router.get("/plc-environments/template", response_model=PlcEnvironmentSettingsSchema)
async def read_plc_environment_template(
    _: User = Depends(get_current_active_user),
    use_case: GetPlcEnvironmentTemplate = Depends(get_plc_environment_template_use_case),
) -> PlcEnvironmentSettingsSchema:
    """The settings of Siemens TIA Portal, which a new environment starts from."""
    result = await use_case.execute()
    return PlcEnvironmentSettingsSchema.model_validate(result.model_dump())


@router.post(
    "/plc-environments", response_model=PlcEnvironmentResponse, status_code=status.HTTP_201_CREATED
)
async def create_plc_environment(
    body: PlcEnvironmentSaveRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreatePlcEnvironment = Depends(get_create_plc_environment_use_case),
) -> PlcEnvironmentResponse:
    result = await use_case.execute(actor, SavePlcEnvironmentCommand(**body.model_dump()))
    return PlcEnvironmentResponse.model_validate(result.model_dump())


@router.put("/plc-environments/{environment_id}", response_model=PlcEnvironmentResponse)
async def update_plc_environment(
    environment_id: int,
    body: PlcEnvironmentSaveRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdatePlcEnvironment = Depends(get_update_plc_environment_use_case),
) -> PlcEnvironmentResponse:
    result = await use_case.execute(
        actor, environment_id, SavePlcEnvironmentCommand(**body.model_dump())
    )
    return PlcEnvironmentResponse.model_validate(result.model_dump())


@router.post("/plc-environments/{environment_id}/archive", response_model=PlcEnvironmentResponse)
async def archive_plc_environment(
    environment_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: SetPlcEnvironmentArchived = Depends(get_set_plc_environment_archived_use_case),
) -> PlcEnvironmentResponse:
    result = await use_case.execute(actor, environment_id, archived=True)
    return PlcEnvironmentResponse.model_validate(result.model_dump())


@router.post("/plc-environments/{environment_id}/restore", response_model=PlcEnvironmentResponse)
async def restore_plc_environment(
    environment_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: SetPlcEnvironmentArchived = Depends(get_set_plc_environment_archived_use_case),
) -> PlcEnvironmentResponse:
    result = await use_case.execute(actor, environment_id, archived=False)
    return PlcEnvironmentResponse.model_validate(result.model_dump())
