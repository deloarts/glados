"""
Catalogue item endpoints (BoughtItem, what a part IS).
Manages the central article database: create, read, update, soft-delete.
"""

from datetime import tzinfo

from fastapi import Depends
from fastapi import Query
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.catalogue.adapters.inbound.api.deps.items import get_archive_bought_item_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_bought_item_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_bought_items_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_create_bought_item_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_list_bought_item_merge_targets_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.items import get_merge_bought_item_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_restore_bought_item_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_update_bought_item_use_case
from src.modules.catalogue.adapters.inbound.api.schemas.bought_item_schema import (
    BoughtItemFilterParams,
)
from src.modules.catalogue.adapters.inbound.api.schemas.bought_item_schema import (
    BoughtItemMergeTargetResponse,
)
from src.modules.catalogue.adapters.inbound.api.schemas.bought_item_schema import (
    BoughtItemWebCreateRequest,
)
from src.modules.catalogue.adapters.inbound.api.schemas.bought_item_schema import (
    BoughtItemWebResponse,
)
from src.modules.catalogue.adapters.inbound.api.schemas.bought_item_schema import (
    BoughtItemWebUpdateRequest,
)
from src.modules.catalogue.adapters.inbound.api.schemas.bought_item_schema import (
    MergeBoughtItemRequest,
)
from src.modules.catalogue.application.dto.bought_item_dto import BoughtItemMergeTargetResult
from src.modules.catalogue.application.dto.bought_item_dto import BoughtItemResult
from src.modules.catalogue.application.dto.bought_item_dto import CreateBoughtItemCommand
from src.modules.catalogue.application.dto.bought_item_dto import MergeBoughtItemCommand
from src.modules.catalogue.application.dto.bought_item_dto import UpdateBoughtItemCommand
from src.modules.catalogue.application.use_cases.bought_item.archive_bought_item import (
    ArchiveBoughtItem,
)
from src.modules.catalogue.application.use_cases.bought_item.create_bought_item import (
    CreateBoughtItem,
)
from src.modules.catalogue.application.use_cases.bought_item.get_bought_item import GetBoughtItem
from src.modules.catalogue.application.use_cases.bought_item.get_bought_item import GetBoughtItems
from src.modules.catalogue.application.use_cases.bought_item.list_bought_item_merge_targets import (
    ListBoughtItemMergeTargets,
)
from src.modules.catalogue.application.use_cases.bought_item.merge_bought_item import (
    MergeBoughtItem,
)
from src.modules.catalogue.application.use_cases.bought_item.restore_bought_item import (
    RestoreBoughtItem,
)
from src.modules.catalogue.application.use_cases.bought_item.update_bought_item import (
    UpdateBoughtItem,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.misc import get_tenant_zone
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/", response_model=PageResponse[BoughtItemWebResponse])
async def read_bought_items(
    params: BoughtItemFilterParams = Depends(),
    actor: User = Depends(get_current_active_user),
    zone: tzinfo = Depends(get_tenant_zone),
    use_case: GetBoughtItems = Depends(get_bought_items_use_case),
) -> PageResponse[BoughtItemResult]:
    result = await use_case.execute(params.to_dto(zone), actor=actor)
    return PageResponse.from_result(result, params)


@router.post("/", response_model=BoughtItemWebResponse, status_code=status.HTTP_201_CREATED)
async def create_bought_item(
    body: BoughtItemWebCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateBoughtItem = Depends(get_create_bought_item_use_case),
) -> BoughtItemResult:
    cmd = CreateBoughtItemCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)


@router.get("/{item_id}", response_model=BoughtItemWebResponse)
async def read_bought_item(
    item_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: GetBoughtItem = Depends(get_bought_item_use_case),
) -> BoughtItemResult:
    return await use_case.execute(item_id=item_id, actor=actor)


@router.get("/{item_id}/changelog", response_model=list[str])
async def read_bought_item_changelog(
    item_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetBoughtItem = Depends(get_bought_item_use_case),
) -> list[str]:
    return (await use_case.execute(item_id)).changes


@router.put("/{item_id}", response_model=BoughtItemWebResponse)
async def update_bought_item(
    item_id: int,
    body: BoughtItemWebUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateBoughtItem = Depends(get_update_bought_item_use_case),
) -> BoughtItemResult:
    cmd = UpdateBoughtItemCommand(**body.model_dump())
    return await use_case.execute(actor=actor, item_id=item_id, cmd=cmd)


@router.get("/{item_id}/merge-targets", response_model=list[BoughtItemMergeTargetResponse])
async def read_bought_item_merge_targets(
    item_id: int,
    search: str | None = Query(None, max_length=200),
    limit: int = Query(50, ge=1, le=100),
    actor: User = Depends(get_current_active_user),
    use_case: ListBoughtItemMergeTargets = Depends(get_list_bought_item_merge_targets_use_case),
) -> list[BoughtItemMergeTargetResult]:
    """The items the catalogue search finds for `search`, each with whether
    it may take the merge of item `item_id` and why not."""
    return await use_case.execute(actor=actor, source_id=item_id, search=search, limit=limit)


@router.post("/{item_id}/merge", response_model=BoughtItemWebResponse)
async def merge_bought_item(
    item_id: int,
    body: MergeBoughtItemRequest,
    actor: User = Depends(get_current_active_user),
    use_case: MergeBoughtItem = Depends(get_merge_bought_item_use_case),
) -> BoughtItemResult:
    cmd = MergeBoughtItemCommand(**body.model_dump())
    return await use_case.execute(actor=actor, source_id=item_id, cmd=cmd)


@router.post("/{item_id}/archive", response_model=BoughtItemWebResponse)
async def archive_bought_item(
    item_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: ArchiveBoughtItem = Depends(get_archive_bought_item_use_case),
) -> BoughtItemResult:
    return await use_case.execute(actor=actor, item_id=item_id)


@router.post("/{item_id}/restore", response_model=BoughtItemWebResponse)
async def restore_bought_item(
    item_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: RestoreBoughtItem = Depends(get_restore_bought_item_use_case),
) -> BoughtItemResult:
    return await use_case.execute(actor=actor, item_id=item_id)
