"""
Catalogue item endpoints (SourceItem, a made item's raw material input).
Manages the source item catalogue: create, read, update, soft-delete.
"""

from datetime import tzinfo
from typing import Annotated

from fastapi import Depends
from fastapi import Query
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.catalogue.adapters.inbound.api.deps.items import get_archive_source_item_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_create_source_item_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_restore_source_item_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_source_item_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_source_items_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_update_source_item_use_case
from src.modules.catalogue.adapters.inbound.api.schemas.source_item_schema import (
    SourceItemUpdateRequest,
)
from src.modules.catalogue.adapters.inbound.api.schemas.source_item_schema import (
    SourceItemWebCreateRequest,
)
from src.modules.catalogue.adapters.inbound.api.schemas.source_item_schema import (
    SourceItemWebFilterParams,
)
from src.modules.catalogue.adapters.inbound.api.schemas.source_item_schema import (
    SourceItemWebResponse,
)
from src.modules.catalogue.application.dto.source_item_dto import CreateSourceItemCommand
from src.modules.catalogue.application.dto.source_item_dto import SourceItemResult
from src.modules.catalogue.application.dto.source_item_dto import UpdateSourceItemCommand
from src.modules.catalogue.application.use_cases.source_item.archive_source_item import (
    ArchiveSourceItem,
)
from src.modules.catalogue.application.use_cases.source_item.create_source_item import (
    CreateSourceItem,
)
from src.modules.catalogue.application.use_cases.source_item.get_source_item import GetSourceItem
from src.modules.catalogue.application.use_cases.source_item.get_source_item import GetSourceItems
from src.modules.catalogue.application.use_cases.source_item.restore_source_item import (
    RestoreSourceItem,
)
from src.modules.catalogue.application.use_cases.source_item.update_source_item import (
    UpdateSourceItem,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.misc import get_tenant_zone
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/", response_model=PageResponse[SourceItemWebResponse])
async def read_source_items(
    # A query-parameter model, not `Depends()`: only this binds `ids` from
    # repeated query keys.
    params: Annotated[SourceItemWebFilterParams, Query()],
    _: User = Depends(get_current_active_user),
    zone: tzinfo = Depends(get_tenant_zone),
    use_case: GetSourceItems = Depends(get_source_items_use_case),
) -> PageResponse[SourceItemResult]:
    result = await use_case.execute(params.to_dto(zone))
    return PageResponse.from_result(result, params)


@router.post("/", response_model=SourceItemWebResponse, status_code=status.HTTP_201_CREATED)
async def create_source_item(
    body: SourceItemWebCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateSourceItem = Depends(get_create_source_item_use_case),
) -> SourceItemResult:
    cmd = CreateSourceItemCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)


@router.get("/{item_id}", response_model=SourceItemWebResponse)
async def read_source_item(
    item_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetSourceItem = Depends(get_source_item_use_case),
) -> SourceItemResult:
    return await use_case.execute(item_id=item_id)


@router.get("/{item_id}/changelog", response_model=list[str])
async def read_source_item_changelog(
    item_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetSourceItem = Depends(get_source_item_use_case),
) -> list[str]:
    return (await use_case.execute(item_id=item_id)).changes


@router.put("/{item_id}", response_model=SourceItemWebResponse)
async def update_source_item(
    item_id: int,
    body: SourceItemUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateSourceItem = Depends(get_update_source_item_use_case),
) -> SourceItemResult:
    cmd = UpdateSourceItemCommand(**body.model_dump())
    return await use_case.execute(actor=actor, item_id=item_id, cmd=cmd)


@router.post("/{item_id}/archive", response_model=SourceItemWebResponse)
async def archive_source_item(
    item_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: ArchiveSourceItem = Depends(get_archive_source_item_use_case),
) -> SourceItemResult:
    return await use_case.execute(actor=actor, item_id=item_id)


@router.post("/{item_id}/restore", response_model=SourceItemWebResponse)
async def restore_source_item(
    item_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: RestoreSourceItem = Depends(get_restore_source_item_use_case),
) -> SourceItemResult:
    return await use_case.execute(actor=actor, item_id=item_id)
