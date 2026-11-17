"""
Source item type endpoints, manages the catalogue type/labelling
referenced by source items.
"""

from datetime import tzinfo

from fastapi import Depends
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_archive_source_item_type_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_create_source_item_type_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.items import get_move_source_item_type_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_place_source_item_type_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_restore_source_item_type_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.items import get_source_item_type_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_source_item_types_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_update_source_item_type_use_case,
)
from src.modules.catalogue.adapters.inbound.api.schemas.source_item_type_schema import (
    SourceItemTypeCreateRequest,
)
from src.modules.catalogue.adapters.inbound.api.schemas.source_item_type_schema import (
    SourceItemTypeFilterParams,
)
from src.modules.catalogue.adapters.inbound.api.schemas.source_item_type_schema import (
    SourceItemTypeUpdateRequest,
)
from src.modules.catalogue.adapters.inbound.api.schemas.source_item_type_schema import (
    SourceItemTypeWebResponse,
)
from src.modules.catalogue.application.dto.source_item_type_dto import CreateSourceItemTypeCommand
from src.modules.catalogue.application.dto.source_item_type_dto import UpdateSourceItemTypeCommand
from src.modules.catalogue.application.use_cases.source_item_type.archive_source_item_type import (
    ArchiveSourceItemType,
)
from src.modules.catalogue.application.use_cases.source_item_type.create_source_item_type import (
    CreateSourceItemType,
)
from src.modules.catalogue.application.use_cases.source_item_type.get_source_item_type import (
    GetSourceItemType,
)
from src.modules.catalogue.application.use_cases.source_item_type.get_source_item_type import (
    GetSourceItemTypes,
)
from src.modules.catalogue.application.use_cases.source_item_type.move_source_item_type import (
    MoveSourceItemType,
)
from src.modules.catalogue.application.use_cases.source_item_type.move_source_item_type import (
    PlaceSourceItemType,
)
from src.modules.catalogue.application.use_cases.source_item_type.restore_source_item_type import (
    RestoreSourceItemType,
)
from src.modules.catalogue.application.use_cases.source_item_type.update_source_item_type import (
    UpdateSourceItemType,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.misc import get_label_languages
from src.modules.platform.adapters.inbound.api.deps.misc import get_tenant_zone
from src.modules.platform.adapters.inbound.api.schemas.list_move_schema import ListMoveRequest
from src.modules.platform.adapters.inbound.api.schemas.list_move_schema import ListPlaceRequest
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/", response_model=PageResponse[SourceItemTypeWebResponse])
async def read_source_item_types(
    params: SourceItemTypeFilterParams = Depends(),
    _: User = Depends(get_current_active_user),
    zone: tzinfo = Depends(get_tenant_zone),
    languages: tuple[str, ...] = Depends(get_label_languages),
    use_case: GetSourceItemTypes = Depends(get_source_item_types_use_case),
) -> PageResponse[SourceItemTypeWebResponse]:
    result = await use_case.execute(params.to_dto(zone, languages))
    return PageResponse.from_result(result, params, item_model=SourceItemTypeWebResponse)


@router.post("/", response_model=SourceItemTypeWebResponse, status_code=status.HTTP_201_CREATED)
async def create_source_item_type(
    body: SourceItemTypeCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateSourceItemType = Depends(get_create_source_item_type_use_case),
) -> SourceItemTypeWebResponse:
    cmd = CreateSourceItemTypeCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, cmd=cmd)
    return SourceItemTypeWebResponse.model_validate(result.model_dump())


@router.get("/{source_item_type_id}", response_model=SourceItemTypeWebResponse)
async def read_source_item_type(
    source_item_type_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetSourceItemType = Depends(get_source_item_type_use_case),
) -> SourceItemTypeWebResponse:
    result = await use_case.execute(source_item_type_id=source_item_type_id)
    return SourceItemTypeWebResponse.model_validate(result.model_dump())


@router.get("/{source_item_type_id}/changelog", response_model=list[str])
async def read_source_item_type_changelog(
    source_item_type_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetSourceItemType = Depends(get_source_item_type_use_case),
) -> list[str]:
    return await use_case.changelog(source_item_type_id)


@router.put("/{source_item_type_id}", response_model=SourceItemTypeWebResponse)
async def update_source_item_type(
    source_item_type_id: int,
    body: SourceItemTypeUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateSourceItemType = Depends(get_update_source_item_type_use_case),
) -> SourceItemTypeWebResponse:
    cmd = UpdateSourceItemTypeCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, source_item_type_id=source_item_type_id, cmd=cmd)
    return SourceItemTypeWebResponse.model_validate(result.model_dump())


@router.post("/{source_item_type_id}/archive", response_model=SourceItemTypeWebResponse)
async def archive_source_item_type(
    source_item_type_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: ArchiveSourceItemType = Depends(get_archive_source_item_type_use_case),
) -> SourceItemTypeWebResponse:
    result = await use_case.execute(actor=actor, source_item_type_id=source_item_type_id)
    return SourceItemTypeWebResponse.model_validate(result.model_dump())


@router.post("/{source_item_type_id}/restore", response_model=SourceItemTypeWebResponse)
async def restore_source_item_type(
    source_item_type_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: RestoreSourceItemType = Depends(get_restore_source_item_type_use_case),
) -> SourceItemTypeWebResponse:
    result = await use_case.execute(actor=actor, source_item_type_id=source_item_type_id)
    return SourceItemTypeWebResponse.model_validate(result.model_dump())


@router.post("/{source_item_type_id}/move", status_code=status.HTTP_204_NO_CONTENT)
async def move_source_item_type(
    source_item_type_id: int,
    body: ListMoveRequest,
    actor: User = Depends(get_current_active_user),
    use_case: MoveSourceItemType = Depends(get_move_source_item_type_use_case),
) -> None:
    """Moves the entry one place up or down in the order pickers offer."""
    await use_case.execute(actor, source_item_type_id, body.direction)


@router.post("/{source_item_type_id}/place", status_code=status.HTTP_204_NO_CONTENT)
async def place_source_item_type(
    source_item_type_id: int,
    body: ListPlaceRequest,
    actor: User = Depends(get_current_active_user),
    use_case: PlaceSourceItemType = Depends(get_place_source_item_type_use_case),
) -> None:
    """Puts the type next to another one, as dragging its row does."""
    await use_case.execute(
        actor, source_item_type_id, after_id=body.after_id, before_id=body.before_id
    )
