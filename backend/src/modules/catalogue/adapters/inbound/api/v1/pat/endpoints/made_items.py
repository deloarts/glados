"""
PAT surface, catalogue items: read-only, deliberately. Unlike bought
items, made-item routing (`processes`, steps and groups) is authored in
the CAD file and reaches Glados via PDM ingest (docs/reference/field-ownership.md
sections 2.2 and 2.5): the add-in's only writes to Glados are the named exceptions
elsewhere (source-item creation, PDM-link assertion), never made-item
data. There is therefore no POST/PUT/DELETE and no `/processes/*` route
here; the web's `PUT /made-items/{id}/processes/regroup` stays web-only,
for Glados-owned rows. This is a decision, not an oversight.
"""

from datetime import tzinfo

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_made_item_revisions_by_part_number_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.items import get_made_item_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_made_items_use_case
from src.modules.catalogue.adapters.inbound.api.schemas.made_item_schema import MadeItemFilterParams
from src.modules.catalogue.adapters.inbound.api.schemas.made_item_schema import MadeItemResponse
from src.modules.catalogue.adapters.inbound.api.schemas.made_item_schema import (
    MadeItemRevisionsResponse,
)
from src.modules.catalogue.application.dto.made_item_dto import MadeItemResult
from src.modules.catalogue.application.dto.made_item_dto import MadeItemRevisionsResult
from src.modules.catalogue.application.use_cases.made_item.get_made_item import GetMadeItem
from src.modules.catalogue.application.use_cases.made_item.get_made_item import GetMadeItems
from src.modules.catalogue.application.use_cases.made_item.get_made_item_revisions_by_part_number import (
    GetMadeItemRevisionsByPartNumber,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_user_pat
from src.modules.platform.adapters.inbound.api.deps.misc import get_tenant_zone
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/", response_model=PageResponse[MadeItemResponse])
async def read_made_items(
    params: MadeItemFilterParams = Depends(),
    _: User = Depends(get_current_user_pat),
    zone: tzinfo = Depends(get_tenant_zone),
    use_case: GetMadeItems = Depends(get_made_items_use_case),
) -> PageResponse[MadeItemResult]:
    result = await use_case.execute(params.to_dto(zone))
    return PageResponse.from_result(result, params)


@router.get("/{item_id}", response_model=MadeItemResponse)
async def read_made_item(
    item_id: int,
    _: User = Depends(get_current_user_pat),
    use_case: GetMadeItem = Depends(get_made_item_use_case),
) -> MadeItemResult:
    return await use_case.execute(item_id=item_id)


@router.get("/partnumber/{part_number}", response_model=MadeItemResponse)
async def read_made_item_by_part_number(
    part_number: str,
    revision: str | None = None,
    _: User = Depends(get_current_user_pat),
    use_case: GetMadeItem = Depends(get_made_item_use_case),
) -> MadeItemResult:
    return await use_case.execute(part_number=part_number, revision=revision)


@router.get(
    "/partnumber/{part_number}/revisions",
    response_model=MadeItemRevisionsResponse,
)
async def read_made_item_revisions_by_part_number(
    part_number: str,
    actor: User = Depends(get_current_user_pat),
    use_case: GetMadeItemRevisionsByPartNumber = Depends(
        get_made_item_revisions_by_part_number_use_case
    ),
) -> MadeItemRevisionsResult:
    return await use_case.execute(actor=actor, part_number=part_number)
