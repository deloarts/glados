"""
Catalogue item endpoints (MadeItem, what a manufactured part IS), plus its
owned, ordered process steps (routing).
"""

from datetime import tzinfo
from typing import Annotated

from fastapi import Depends
from fastapi import Query
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.catalogue.adapters.inbound.api.deps.items import get_archive_made_item_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_create_made_item_process_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_create_made_item_revision_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.items import get_create_made_item_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_delete_made_item_process_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_list_made_item_merge_targets_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.items import get_made_item_revisions_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_made_item_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_made_items_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_merge_made_item_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_regroup_made_item_processes_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_reorder_made_item_processes_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.items import get_restore_made_item_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_update_made_item_process_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.items import get_update_made_item_use_case
from src.modules.catalogue.adapters.inbound.api.schemas.made_item_schema import (
    MadeItemCreateRequest,
)
from src.modules.catalogue.adapters.inbound.api.schemas.made_item_schema import (
    MadeItemCreateRevisionRequest,
)
from src.modules.catalogue.adapters.inbound.api.schemas.made_item_schema import (
    MadeItemMergeTargetResponse,
)
from src.modules.catalogue.adapters.inbound.api.schemas.made_item_schema import (
    MadeItemProcessCreateRequest,
)
from src.modules.catalogue.adapters.inbound.api.schemas.made_item_schema import (
    MadeItemProcessRegroupRequest,
)
from src.modules.catalogue.adapters.inbound.api.schemas.made_item_schema import (
    MadeItemProcessReorderRequest,
)
from src.modules.catalogue.adapters.inbound.api.schemas.made_item_schema import (
    MadeItemProcessUpdateRequest,
)
from src.modules.catalogue.adapters.inbound.api.schemas.made_item_schema import (
    MadeItemProcessWebResponse,
)
from src.modules.catalogue.adapters.inbound.api.schemas.made_item_schema import (
    MadeItemRevisionsResponse,
)
from src.modules.catalogue.adapters.inbound.api.schemas.made_item_schema import (
    MadeItemUpdateRequest,
)
from src.modules.catalogue.adapters.inbound.api.schemas.made_item_schema import (
    MadeItemWebFilterParams,
)
from src.modules.catalogue.adapters.inbound.api.schemas.made_item_schema import MadeItemWebResponse
from src.modules.catalogue.adapters.inbound.api.schemas.made_item_schema import MergeMadeItemRequest
from src.modules.catalogue.application.dto.made_item_dto import CreateMadeItemCommand
from src.modules.catalogue.application.dto.made_item_dto import CreateMadeItemProcessCommand
from src.modules.catalogue.application.dto.made_item_dto import CreateMadeItemRevisionCommand
from src.modules.catalogue.application.dto.made_item_dto import MadeItemMergeTargetResult
from src.modules.catalogue.application.dto.made_item_dto import MadeItemProcessResult
from src.modules.catalogue.application.dto.made_item_dto import MadeItemResult
from src.modules.catalogue.application.dto.made_item_dto import MadeItemRevisionItemCommand
from src.modules.catalogue.application.dto.made_item_dto import MadeItemRevisionsResult
from src.modules.catalogue.application.dto.made_item_dto import MergeMadeItemCommand
from src.modules.catalogue.application.dto.made_item_dto import RegroupMadeItemProcessesCommand
from src.modules.catalogue.application.dto.made_item_dto import ReorderMadeItemProcessesCommand
from src.modules.catalogue.application.dto.made_item_dto import UpdateMadeItemCommand
from src.modules.catalogue.application.dto.made_item_dto import UpdateMadeItemProcessCommand
from src.modules.catalogue.application.use_cases.made_item.archive_made_item import ArchiveMadeItem
from src.modules.catalogue.application.use_cases.made_item.create_made_item import CreateMadeItem
from src.modules.catalogue.application.use_cases.made_item.create_made_item_process import (
    CreateMadeItemProcess,
)
from src.modules.catalogue.application.use_cases.made_item.create_made_item_revision import (
    CreateMadeItemRevision,
)
from src.modules.catalogue.application.use_cases.made_item.delete_made_item_process import (
    DeleteMadeItemProcess,
)
from src.modules.catalogue.application.use_cases.made_item.get_made_item import GetMadeItem
from src.modules.catalogue.application.use_cases.made_item.get_made_item import GetMadeItems
from src.modules.catalogue.application.use_cases.made_item.get_made_item_revisions import (
    GetMadeItemRevisions,
)
from src.modules.catalogue.application.use_cases.made_item.list_made_item_merge_targets import (
    ListMadeItemMergeTargets,
)
from src.modules.catalogue.application.use_cases.made_item.merge_made_item import MergeMadeItem
from src.modules.catalogue.application.use_cases.made_item.regroup_made_item_processes import (
    RegroupMadeItemProcesses,
)
from src.modules.catalogue.application.use_cases.made_item.reorder_made_item_processes import (
    ReorderMadeItemProcesses,
)
from src.modules.catalogue.application.use_cases.made_item.restore_made_item import RestoreMadeItem
from src.modules.catalogue.application.use_cases.made_item.update_made_item import UpdateMadeItem
from src.modules.catalogue.application.use_cases.made_item.update_made_item_process import (
    UpdateMadeItemProcess,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.misc import get_tenant_zone
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/", response_model=PageResponse[MadeItemWebResponse])
async def read_made_items(
    # A query-parameter model, not `Depends()`: only this binds `ids` from
    # repeated query keys.
    params: Annotated[MadeItemWebFilterParams, Query()],
    actor: User = Depends(get_current_active_user),
    zone: tzinfo = Depends(get_tenant_zone),
    use_case: GetMadeItems = Depends(get_made_items_use_case),
) -> PageResponse[MadeItemResult]:
    result = await use_case.execute(params.to_dto(zone), actor=actor)
    return PageResponse.from_result(result, params)


@router.post("/", response_model=MadeItemWebResponse, status_code=status.HTTP_201_CREATED)
async def create_made_item(
    body: MadeItemCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateMadeItem = Depends(get_create_made_item_use_case),
) -> MadeItemResult:
    cmd = CreateMadeItemCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)


@router.get("/{item_id}", response_model=MadeItemWebResponse)
async def read_made_item(
    item_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: GetMadeItem = Depends(get_made_item_use_case),
) -> MadeItemResult:
    return await use_case.execute(item_id=item_id, actor=actor)


@router.get("/{item_id}/changelog", response_model=list[str])
async def read_made_item_changelog(
    item_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetMadeItem = Depends(get_made_item_use_case),
) -> list[str]:
    return (await use_case.execute(item_id)).changes


@router.put("/{item_id}", response_model=MadeItemWebResponse)
async def update_made_item(
    item_id: int,
    body: MadeItemUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateMadeItem = Depends(get_update_made_item_use_case),
) -> MadeItemResult:
    cmd = UpdateMadeItemCommand(**body.model_dump())
    return await use_case.execute(actor=actor, item_id=item_id, cmd=cmd)


@router.get("/{item_id}/merge-targets", response_model=list[MadeItemMergeTargetResponse])
async def read_made_item_merge_targets(
    item_id: int,
    search: str | None = Query(None, max_length=200),
    limit: int = Query(50, ge=1, le=100),
    actor: User = Depends(get_current_active_user),
    use_case: ListMadeItemMergeTargets = Depends(get_list_made_item_merge_targets_use_case),
) -> list[MadeItemMergeTargetResult]:
    """The items the catalogue search finds for `search`, each with whether
    it may take the merge of item `item_id` and why not."""
    return await use_case.execute(actor=actor, source_id=item_id, search=search, limit=limit)


@router.post("/{item_id}/merge", response_model=MadeItemWebResponse)
async def merge_made_item(
    item_id: int,
    body: MergeMadeItemRequest,
    actor: User = Depends(get_current_active_user),
    use_case: MergeMadeItem = Depends(get_merge_made_item_use_case),
) -> MadeItemResult:
    cmd = MergeMadeItemCommand(**body.model_dump())
    return await use_case.execute(actor=actor, source_id=item_id, cmd=cmd)


@router.post("/{item_id}/archive", response_model=MadeItemWebResponse)
async def archive_made_item(
    item_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: ArchiveMadeItem = Depends(get_archive_made_item_use_case),
) -> MadeItemResult:
    return await use_case.execute(actor=actor, item_id=item_id)


@router.post("/{item_id}/restore", response_model=MadeItemWebResponse)
async def restore_made_item(
    item_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: RestoreMadeItem = Depends(get_restore_made_item_use_case),
) -> MadeItemResult:
    return await use_case.execute(actor=actor, item_id=item_id)


# ══════════════════════════════════════════════════════════════════════
# Made-item revisions
# ══════════════════════════════════════════════════════════════════════


@router.get("/{item_id}/revisions", response_model=MadeItemRevisionsResponse)
async def read_made_item_revisions(
    item_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: GetMadeItemRevisions = Depends(get_made_item_revisions_use_case),
) -> MadeItemRevisionsResult:
    return await use_case.execute(actor=actor, item_id=item_id)


@router.post(
    "/{item_id}/revisions", response_model=MadeItemWebResponse, status_code=status.HTTP_201_CREATED
)
async def create_made_item_revision(
    item_id: int,
    body: MadeItemCreateRevisionRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateMadeItemRevision = Depends(get_create_made_item_revision_use_case),
) -> MadeItemResult:
    cmd = CreateMadeItemRevisionCommand(
        predecessor_status=body.predecessor_status,
        item=MadeItemRevisionItemCommand(**body.item.model_dump()),
    )
    return await use_case.execute(actor=actor, item_id=item_id, cmd=cmd)


# ══════════════════════════════════════════════════════════════════════
# MadeItemProcess (routing steps)
# ══════════════════════════════════════════════════════════════════════


@router.post(
    "/{item_id}/processes",
    response_model=MadeItemProcessWebResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_made_item_process(
    item_id: int,
    body: MadeItemProcessCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateMadeItemProcess = Depends(get_create_made_item_process_use_case),
) -> MadeItemProcessResult:
    cmd = CreateMadeItemProcessCommand(**body.model_dump())
    return await use_case.execute(actor=actor, made_item_id=item_id, cmd=cmd)


@router.put("/{item_id}/processes/reorder", response_model=list[MadeItemProcessWebResponse])
async def reorder_made_item_processes(
    item_id: int,
    body: MadeItemProcessReorderRequest,
    actor: User = Depends(get_current_active_user),
    use_case: ReorderMadeItemProcesses = Depends(get_reorder_made_item_processes_use_case),
) -> list[MadeItemProcessResult]:
    cmd = ReorderMadeItemProcessesCommand(**body.model_dump())
    return await use_case.execute(actor=actor, made_item_id=item_id, cmd=cmd)


@router.put("/{item_id}/processes/regroup", response_model=list[MadeItemProcessWebResponse])
async def regroup_made_item_processes(
    item_id: int,
    body: MadeItemProcessRegroupRequest,
    actor: User = Depends(get_current_active_user),
    use_case: RegroupMadeItemProcesses = Depends(get_regroup_made_item_processes_use_case),
) -> list[MadeItemProcessResult]:
    cmd = RegroupMadeItemProcessesCommand(**body.model_dump())
    return await use_case.execute(actor=actor, made_item_id=item_id, cmd=cmd)


@router.put("/{item_id}/processes/{process_id}", response_model=MadeItemProcessWebResponse)
async def update_made_item_process(
    item_id: int,
    process_id: int,
    body: MadeItemProcessUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateMadeItemProcess = Depends(get_update_made_item_process_use_case),
) -> MadeItemProcessResult:
    cmd = UpdateMadeItemProcessCommand(**body.model_dump())
    return await use_case.execute(actor=actor, item_id=item_id, process_id=process_id, cmd=cmd)


@router.delete("/{item_id}/processes/{process_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_made_item_process(
    item_id: int,
    process_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: DeleteMadeItemProcess = Depends(get_delete_made_item_process_use_case),
) -> None:
    await use_case.execute(actor=actor, item_id=item_id, process_id=process_id)
