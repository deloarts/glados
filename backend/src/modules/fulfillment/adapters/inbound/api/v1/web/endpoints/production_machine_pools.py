"""
MachinePool catalogue endpoints. Prefix `/production-machine-pools`,
flat kebab-case, matching this repo's actual convention (see
production_lots.py's docstring, which pre-commits to this prefix).
"""

from fastapi import Depends
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_archive_machine_pool_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_create_machine_pool_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import get_machine_pool_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.production import get_machine_pools_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_place_machine_pool_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_restore_machine_pool_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_update_machine_pool_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.machine_pool_schema import (
    MachinePoolCreateRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.machine_pool_schema import (
    MachinePoolFilterParams,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.machine_pool_schema import (
    MachinePoolResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.machine_pool_schema import (
    MachinePoolUpdateRequest,
)
from src.modules.fulfillment.application.dto.machine_pool_dto import CreateMachinePoolCommand
from src.modules.fulfillment.application.dto.machine_pool_dto import MachinePoolResult
from src.modules.fulfillment.application.dto.machine_pool_dto import UpdateMachinePoolCommand
from src.modules.fulfillment.application.use_cases.machine_pool.archive_pool import (
    ArchiveMachinePool,
)
from src.modules.fulfillment.application.use_cases.machine_pool.create_pool import CreateMachinePool
from src.modules.fulfillment.application.use_cases.machine_pool.get_pool import GetMachinePool
from src.modules.fulfillment.application.use_cases.machine_pool.get_pool import GetMachinePools
from src.modules.fulfillment.application.use_cases.machine_pool.place_pool import PlaceMachinePool
from src.modules.fulfillment.application.use_cases.machine_pool.restore_pool import (
    RestoreMachinePool,
)
from src.modules.fulfillment.application.use_cases.machine_pool.update_pool import UpdateMachinePool
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.schemas.list_move_schema import ListPlaceRequest
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/", response_model=PageResponse[MachinePoolResponse])
async def read_production_machine_pools(
    params: MachinePoolFilterParams = Depends(),
    _: User = Depends(get_current_active_user),
    use_case: GetMachinePools = Depends(get_machine_pools_use_case),
) -> PageResponse[MachinePoolResult]:
    result = await use_case.execute(params.to_dto())
    return PageResponse.from_result(result, params)


@router.post("/", response_model=MachinePoolResponse, status_code=status.HTTP_201_CREATED)
async def create_machine_pool(
    body: MachinePoolCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateMachinePool = Depends(get_create_machine_pool_use_case),
) -> MachinePoolResult:
    cmd = CreateMachinePoolCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)


@router.get("/{pool_id}", response_model=MachinePoolResponse)
async def read_production_machine_pool(
    pool_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetMachinePool = Depends(get_machine_pool_use_case),
) -> MachinePoolResult:
    return await use_case.execute(pool_id=pool_id)


@router.patch("/{pool_id}", response_model=MachinePoolResponse)
async def update_machine_pool(
    pool_id: int,
    body: MachinePoolUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateMachinePool = Depends(get_update_machine_pool_use_case),
) -> MachinePoolResult:
    cmd = UpdateMachinePoolCommand(**body.model_dump())
    return await use_case.execute(actor=actor, pool_id=pool_id, cmd=cmd)


@router.post("/{pool_id}/archive", response_model=MachinePoolResponse)
async def archive_machine_pool(
    pool_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: ArchiveMachinePool = Depends(get_archive_machine_pool_use_case),
) -> MachinePoolResult:
    return await use_case.execute(actor=actor, pool_id=pool_id)


@router.post("/{pool_id}/restore", response_model=MachinePoolResponse)
async def restore_machine_pool(
    pool_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: RestoreMachinePool = Depends(get_restore_machine_pool_use_case),
) -> MachinePoolResult:
    return await use_case.execute(actor=actor, pool_id=pool_id)


@router.post("/{pool_id}/place", status_code=status.HTTP_204_NO_CONTENT)
async def place_machine_pool(
    pool_id: int,
    body: ListPlaceRequest,
    actor: User = Depends(get_current_active_user),
    use_case: PlaceMachinePool = Depends(get_place_machine_pool_use_case),
) -> None:
    """Puts the pool next to another one, as dragging its row does."""
    await use_case.execute(actor, pool_id, after_id=body.after_id, before_id=body.before_id)
