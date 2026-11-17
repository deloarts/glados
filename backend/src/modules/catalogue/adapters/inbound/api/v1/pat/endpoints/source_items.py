"""
PAT surface, source item catalogue access: read, and create. The add-in
creates source items directly (raw-material specs it discovers in CAD
have no other path into Glados); everything else about the aggregate
(update, archive, restore) stays web-only, mirroring the read/create-only
shape of the other catalogue PAT surfaces.
"""

from datetime import tzinfo

from fastapi import Depends
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.catalogue.adapters.inbound.api.deps.items import get_create_source_item_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_source_item_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_source_items_use_case
from src.modules.catalogue.adapters.inbound.api.schemas.source_item_schema import (
    SourceItemCreateRequest,
)
from src.modules.catalogue.adapters.inbound.api.schemas.source_item_schema import (
    SourceItemFilterParams,
)
from src.modules.catalogue.adapters.inbound.api.schemas.source_item_schema import SourceItemResponse
from src.modules.catalogue.application.dto.source_item_dto import CreateSourceItemCommand
from src.modules.catalogue.application.dto.source_item_dto import SourceItemResult
from src.modules.catalogue.application.use_cases.source_item.create_source_item import (
    CreateSourceItem,
)
from src.modules.catalogue.application.use_cases.source_item.get_source_item import GetSourceItem
from src.modules.catalogue.application.use_cases.source_item.get_source_item import GetSourceItems
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_user_pat
from src.modules.platform.adapters.inbound.api.deps.misc import get_tenant_zone
from src.modules.platform.adapters.inbound.api.idempotency import Idempotency
from src.modules.platform.adapters.inbound.api.idempotency import get_pat_idempotency
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.idempotency_key import ResourceRef
from src.modules.platform.domain.entities.user import User

router = APIRouter()

# The resource kind an idempotent create records.
_SOURCE_ITEM = "source_item"


@router.get("/", response_model=PageResponse[SourceItemResponse])
async def read_source_items(
    params: SourceItemFilterParams = Depends(),
    _: User = Depends(get_current_user_pat),
    zone: tzinfo = Depends(get_tenant_zone),
    use_case: GetSourceItems = Depends(get_source_items_use_case),
) -> PageResponse[SourceItemResult]:
    result = await use_case.execute(params.to_dto(zone))
    return PageResponse.from_result(result, params)


@router.post("/", response_model=SourceItemResponse, status_code=status.HTTP_201_CREATED)
async def create_source_item(
    body: SourceItemCreateRequest,
    actor: User = Depends(get_current_user_pat),
    use_case: CreateSourceItem = Depends(get_create_source_item_use_case),
    idempotency: Idempotency = Depends(get_pat_idempotency),
    reader: GetSourceItem = Depends(get_source_item_use_case),
) -> SourceItemResult:
    """With an Idempotency-Key, a retry after a lost answer is answered with
    the source item the first request created, so no second one is created and
    no second number is drawn."""
    cmd = CreateSourceItemCommand(**body.model_dump())
    return await idempotency.run(
        lambda: use_case.execute(actor=actor, cmd=cmd),
        written=lambda created: [ResourceRef(_SOURCE_ITEM, created.id)],
        replay=lambda refs: reader.execute(item_id=refs[0].id),
    )


@router.get("/{item_id}", response_model=SourceItemResponse)
async def read_source_item(
    item_id: int,
    _: User = Depends(get_current_user_pat),
    use_case: GetSourceItem = Depends(get_source_item_use_case),
) -> SourceItemResult:
    return await use_case.execute(item_id=item_id)
