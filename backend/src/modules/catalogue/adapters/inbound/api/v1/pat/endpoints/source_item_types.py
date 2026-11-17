"""
PAT surface, read-only source item type access.
"""

from datetime import tzinfo

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.catalogue.adapters.inbound.api.deps.items import get_source_item_type_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_source_item_types_use_case
from src.modules.catalogue.adapters.inbound.api.schemas.source_item_type_schema import (
    SourceItemTypeFilterParams,
)
from src.modules.catalogue.adapters.inbound.api.schemas.source_item_type_schema import (
    SourceItemTypeResponse,
)
from src.modules.catalogue.application.use_cases.source_item_type.get_source_item_type import (
    GetSourceItemType,
)
from src.modules.catalogue.application.use_cases.source_item_type.get_source_item_type import (
    GetSourceItemTypes,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_user_pat
from src.modules.platform.adapters.inbound.api.deps.misc import get_tenant_zone
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.label_languages import label_languages

router = APIRouter()


@router.get("/", response_model=PageResponse[SourceItemTypeResponse])
async def read_source_item_types(
    params: SourceItemTypeFilterParams = Depends(),
    _: User = Depends(get_current_user_pat),
    zone: tzinfo = Depends(get_tenant_zone),
    use_case: GetSourceItemTypes = Depends(get_source_item_types_use_case),
) -> PageResponse[SourceItemTypeResponse]:
    result = await use_case.execute(params.to_dto(zone, label_languages()))
    return PageResponse.from_result(result, params, item_model=SourceItemTypeResponse)


@router.get("/{source_item_type_id}", response_model=SourceItemTypeResponse)
async def read_source_item_type(
    source_item_type_id: int,
    _: User = Depends(get_current_user_pat),
    use_case: GetSourceItemType = Depends(get_source_item_type_use_case),
) -> SourceItemTypeResponse:
    result = await use_case.execute(source_item_type_id=source_item_type_id)
    return SourceItemTypeResponse.model_validate(result.model_dump())
