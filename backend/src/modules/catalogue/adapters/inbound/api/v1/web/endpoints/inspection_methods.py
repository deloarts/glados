"""
Inspection method endpoints, manages the catalogue of QA checkpoints
referenced by lot/made-item inspection steps.
"""

from datetime import tzinfo

from fastapi import Depends
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_archive_inspection_method_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_create_inspection_method_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.items import get_inspection_method_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_inspection_methods_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_move_inspection_method_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_place_inspection_method_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_restore_inspection_method_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_update_inspection_method_use_case,
)
from src.modules.catalogue.adapters.inbound.api.schemas.inspection_method_schema import (
    InspectionMethodCreateRequest,
)
from src.modules.catalogue.adapters.inbound.api.schemas.inspection_method_schema import (
    InspectionMethodFilterParams,
)
from src.modules.catalogue.adapters.inbound.api.schemas.inspection_method_schema import (
    InspectionMethodUpdateRequest,
)
from src.modules.catalogue.adapters.inbound.api.schemas.inspection_method_schema import (
    InspectionMethodWebResponse,
)
from src.modules.catalogue.application.dto.inspection_method_dto import (
    CreateInspectionMethodCommand,
)
from src.modules.catalogue.application.dto.inspection_method_dto import (
    UpdateInspectionMethodCommand,
)
from src.modules.catalogue.application.use_cases.inspection_method.archive_inspection_method import (
    ArchiveInspectionMethod,
)
from src.modules.catalogue.application.use_cases.inspection_method.create_inspection_method import (
    CreateInspectionMethod,
)
from src.modules.catalogue.application.use_cases.inspection_method.get_inspection_method import (
    GetInspectionMethod,
)
from src.modules.catalogue.application.use_cases.inspection_method.get_inspection_method import (
    GetInspectionMethods,
)
from src.modules.catalogue.application.use_cases.inspection_method.move_inspection_method import (
    MoveInspectionMethod,
)
from src.modules.catalogue.application.use_cases.inspection_method.move_inspection_method import (
    PlaceInspectionMethod,
)
from src.modules.catalogue.application.use_cases.inspection_method.restore_inspection_method import (
    RestoreInspectionMethod,
)
from src.modules.catalogue.application.use_cases.inspection_method.update_inspection_method import (
    UpdateInspectionMethod,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.misc import get_label_languages
from src.modules.platform.adapters.inbound.api.deps.misc import get_tenant_zone
from src.modules.platform.adapters.inbound.api.schemas.list_move_schema import ListMoveRequest
from src.modules.platform.adapters.inbound.api.schemas.list_move_schema import ListPlaceRequest
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/", response_model=PageResponse[InspectionMethodWebResponse])
async def read_inspection_methods(
    params: InspectionMethodFilterParams = Depends(),
    _: User = Depends(get_current_active_user),
    zone: tzinfo = Depends(get_tenant_zone),
    languages: tuple[str, ...] = Depends(get_label_languages),
    use_case: GetInspectionMethods = Depends(get_inspection_methods_use_case),
) -> PageResponse[InspectionMethodWebResponse]:
    result = await use_case.execute(params.to_dto(zone, languages))
    return PageResponse.from_result(result, params, item_model=InspectionMethodWebResponse)


@router.post("/", response_model=InspectionMethodWebResponse, status_code=status.HTTP_201_CREATED)
async def create_inspection_method(
    body: InspectionMethodCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateInspectionMethod = Depends(get_create_inspection_method_use_case),
) -> InspectionMethodWebResponse:
    cmd = CreateInspectionMethodCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, cmd=cmd)
    return InspectionMethodWebResponse.model_validate(result.model_dump())


@router.get("/{inspection_method_id}", response_model=InspectionMethodWebResponse)
async def read_inspection_method(
    inspection_method_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetInspectionMethod = Depends(get_inspection_method_use_case),
) -> InspectionMethodWebResponse:
    result = await use_case.execute(inspection_method_id=inspection_method_id)
    return InspectionMethodWebResponse.model_validate(result.model_dump())


@router.get("/{inspection_method_id}/changelog", response_model=list[str])
async def read_inspection_method_changelog(
    inspection_method_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetInspectionMethod = Depends(get_inspection_method_use_case),
) -> list[str]:
    return await use_case.changelog(inspection_method_id)


@router.put("/{inspection_method_id}", response_model=InspectionMethodWebResponse)
async def update_inspection_method(
    inspection_method_id: int,
    body: InspectionMethodUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateInspectionMethod = Depends(get_update_inspection_method_use_case),
) -> InspectionMethodWebResponse:
    cmd = UpdateInspectionMethodCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, inspection_method_id=inspection_method_id, cmd=cmd)
    return InspectionMethodWebResponse.model_validate(result.model_dump())


@router.post("/{inspection_method_id}/archive", response_model=InspectionMethodWebResponse)
async def archive_inspection_method(
    inspection_method_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: ArchiveInspectionMethod = Depends(get_archive_inspection_method_use_case),
) -> InspectionMethodWebResponse:
    result = await use_case.execute(actor=actor, inspection_method_id=inspection_method_id)
    return InspectionMethodWebResponse.model_validate(result.model_dump())


@router.post("/{inspection_method_id}/restore", response_model=InspectionMethodWebResponse)
async def restore_inspection_method(
    inspection_method_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: RestoreInspectionMethod = Depends(get_restore_inspection_method_use_case),
) -> InspectionMethodWebResponse:
    result = await use_case.execute(actor=actor, inspection_method_id=inspection_method_id)
    return InspectionMethodWebResponse.model_validate(result.model_dump())


@router.post("/{inspection_method_id}/move", status_code=status.HTTP_204_NO_CONTENT)
async def move_inspection_method(
    inspection_method_id: int,
    body: ListMoveRequest,
    actor: User = Depends(get_current_active_user),
    use_case: MoveInspectionMethod = Depends(get_move_inspection_method_use_case),
) -> None:
    """Moves the entry one place up or down in the order pickers offer."""
    await use_case.execute(actor, inspection_method_id, body.direction)


@router.post("/{inspection_method_id}/place", status_code=status.HTTP_204_NO_CONTENT)
async def place_inspection_method(
    inspection_method_id: int,
    body: ListPlaceRequest,
    actor: User = Depends(get_current_active_user),
    use_case: PlaceInspectionMethod = Depends(get_place_inspection_method_use_case),
) -> None:
    """Puts the method next to another one, as dragging its row does."""
    await use_case.execute(
        actor, inspection_method_id, after_id=body.after_id, before_id=body.before_id
    )
