"""
PAT surface, catalogue items: read, create, update.
External scripts and tools (e.g. the SolidWorks addin) can look up,
create and update catalogue items.
"""

from datetime import tzinfo

from fastapi import Depends
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.catalogue.adapters.inbound.api.deps.items import get_bought_item_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_bought_items_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_create_bought_item_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_update_bought_item_use_case
from src.modules.catalogue.adapters.inbound.api.schemas.bought_item_schema import (
    BoughtItemCreateRequest,
)
from src.modules.catalogue.adapters.inbound.api.schemas.bought_item_schema import (
    BoughtItemFilterParams,
)
from src.modules.catalogue.adapters.inbound.api.schemas.bought_item_schema import BoughtItemResponse
from src.modules.catalogue.adapters.inbound.api.schemas.bought_item_schema import (
    BoughtItemUpdateRequest,
)
from src.modules.catalogue.application.dto.bought_item_dto import BoughtItemResult
from src.modules.catalogue.application.dto.bought_item_dto import CreateBoughtItemCommand
from src.modules.catalogue.application.dto.bought_item_dto import UpdateBoughtItemCommand
from src.modules.catalogue.application.use_cases.bought_item.create_bought_item import (
    CreateBoughtItem,
)
from src.modules.catalogue.application.use_cases.bought_item.get_bought_item import GetBoughtItem
from src.modules.catalogue.application.use_cases.bought_item.get_bought_item import GetBoughtItems
from src.modules.catalogue.application.use_cases.bought_item.update_bought_item import (
    UpdateBoughtItem,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_user_pat
from src.modules.platform.adapters.inbound.api.deps.misc import get_tenant_zone
from src.modules.platform.adapters.inbound.api.idempotency import Idempotency
from src.modules.platform.adapters.inbound.api.idempotency import get_pat_idempotency
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.idempotency_key import ResourceRef
from src.modules.platform.domain.entities.user import User

router = APIRouter()

# The resource kind an idempotent create records.
_BOUGHT_ITEM = "bought_item"


@router.get("/", response_model=PageResponse[BoughtItemResponse])
async def read_bought_items(
    params: BoughtItemFilterParams = Depends(),
    _: User = Depends(get_current_user_pat),
    zone: tzinfo = Depends(get_tenant_zone),
    use_case: GetBoughtItems = Depends(get_bought_items_use_case),
) -> PageResponse[BoughtItemResult]:
    result = await use_case.execute(params.to_dto(zone))
    return PageResponse.from_result(result, params)


@router.post("/", response_model=BoughtItemResponse, status_code=status.HTTP_201_CREATED)
async def create_bought_item(
    body: BoughtItemCreateRequest,
    actor: User = Depends(get_current_user_pat),
    use_case: CreateBoughtItem = Depends(get_create_bought_item_use_case),
    idempotency: Idempotency = Depends(get_pat_idempotency),
    reader: GetBoughtItem = Depends(get_bought_item_use_case),
) -> BoughtItemResult:
    """With an Idempotency-Key, a retry after a lost answer is answered with
    the bought item the first request created, so no second one is created and
    no second number is drawn."""
    cmd = CreateBoughtItemCommand(**body.model_dump())
    return await idempotency.run(
        lambda: use_case.execute(actor=actor, cmd=cmd),
        written=lambda created: [ResourceRef(_BOUGHT_ITEM, created.id)],
        replay=lambda refs: reader.execute(item_id=refs[0].id),
    )


@router.get("/{item_id}", response_model=BoughtItemResponse)
async def read_bought_item(
    item_id: int,
    _: User = Depends(get_current_user_pat),
    use_case: GetBoughtItem = Depends(get_bought_item_use_case),
) -> BoughtItemResult:
    return await use_case.execute(item_id=item_id)


@router.put("/{item_id}", response_model=BoughtItemResponse)
async def update_bought_item(
    item_id: int,
    body: BoughtItemUpdateRequest,
    actor: User = Depends(get_current_user_pat),
    use_case: UpdateBoughtItem = Depends(get_update_bought_item_use_case),
) -> BoughtItemResult:
    cmd = UpdateBoughtItemCommand(**body.model_dump())
    return await use_case.execute(actor=actor, item_id=item_id, cmd=cmd)


@router.get("/partnumber/{part_number}", response_model=BoughtItemResponse)
async def read_bought_item_by_part_number(
    part_number: str,
    _: User = Depends(get_current_user_pat),
    use_case: GetBoughtItem = Depends(get_bought_item_use_case),
) -> BoughtItemResult:
    return await use_case.execute(part_number=part_number)
