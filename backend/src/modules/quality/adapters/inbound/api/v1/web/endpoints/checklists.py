"""
Inspection checklists of projects, products and single users, with their
revisions. Every route only requires login; permissions are checked in the
use cases (see ChecklistRules).
"""

from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query
from fastapi import status

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.user import User
from src.modules.quality.adapters.inbound.api.deps.checklists import (
    get_checklist_by_public_id_use_case,
)
from src.modules.quality.adapters.inbound.api.deps.checklists import (
    get_checklist_revisions_use_case,
)
from src.modules.quality.adapters.inbound.api.deps.checklists import get_checklist_use_case
from src.modules.quality.adapters.inbound.api.deps.checklists import get_checklists_use_case
from src.modules.quality.adapters.inbound.api.deps.checklists import get_create_checklist_use_case
from src.modules.quality.adapters.inbound.api.deps.checklists import get_delete_checklist_use_case
from src.modules.quality.adapters.inbound.api.deps.checklists import get_lock_checklist_use_case
from src.modules.quality.adapters.inbound.api.deps.checklists import (
    get_mark_checklist_invalid_use_case,
)
from src.modules.quality.adapters.inbound.api.deps.checklists import get_release_checklist_use_case
from src.modules.quality.adapters.inbound.api.deps.checklists import get_revise_checklist_use_case
from src.modules.quality.adapters.inbound.api.deps.checklists import get_unlock_checklist_use_case
from src.modules.quality.adapters.inbound.api.deps.checklists import get_update_checklist_use_case
from src.modules.quality.adapters.inbound.api.schemas.checklist_schema import ChecklistCreateRequest
from src.modules.quality.adapters.inbound.api.schemas.checklist_schema import ChecklistFilterParams
from src.modules.quality.adapters.inbound.api.schemas.checklist_schema import ChecklistResponse
from src.modules.quality.adapters.inbound.api.schemas.checklist_schema import ChecklistReviseRequest
from src.modules.quality.adapters.inbound.api.schemas.checklist_schema import (
    ChecklistSummaryResponse,
)
from src.modules.quality.adapters.inbound.api.schemas.checklist_schema import ChecklistUpdateRequest
from src.modules.quality.adapters.inbound.api.schemas.controlled_document_schema import (
    DocumentLockRequest,
)
from src.modules.quality.adapters.inbound.api.schemas.controlled_document_schema import (
    DocumentReasonRequest,
)
from src.modules.quality.application.dto.checklist_dto import ChecklistResult
from src.modules.quality.application.dto.checklist_dto import ChecklistSummaryResult
from src.modules.quality.application.dto.checklist_dto import CreateChecklistCommand
from src.modules.quality.application.dto.checklist_dto import ReviseChecklistCommand
from src.modules.quality.application.dto.checklist_dto import UpdateChecklistCommand
from src.modules.quality.application.dto.controlled_document_dto import LockCommand
from src.modules.quality.application.dto.controlled_document_dto import MarkInvalidCommand
from src.modules.quality.application.use_cases.checklist.delete_checklist import DeleteChecklist
from src.modules.quality.application.use_cases.checklist.get_checklists import GetChecklist
from src.modules.quality.application.use_cases.checklist.get_checklists import (
    GetChecklistByPublicId,
)
from src.modules.quality.application.use_cases.checklist.get_checklists import GetChecklistRevisions
from src.modules.quality.application.use_cases.checklist.get_checklists import GetChecklists
from src.modules.quality.application.use_cases.checklist.lock_checklist import LockChecklist
from src.modules.quality.application.use_cases.checklist.lock_checklist import UnlockChecklist
from src.modules.quality.application.use_cases.checklist.release_checklist import (
    MarkChecklistInvalid,
)
from src.modules.quality.application.use_cases.checklist.release_checklist import ReleaseChecklist
from src.modules.quality.application.use_cases.checklist.revise_checklist import ReviseChecklist
from src.modules.quality.application.use_cases.checklist.save_checklist import CreateChecklist
from src.modules.quality.application.use_cases.checklist.save_checklist import UpdateChecklist

router = APIRouter()


@router.get("", response_model=PageResponse[ChecklistSummaryResponse])
async def read_checklists(
    params: ChecklistFilterParams = Depends(),
    actor: User = Depends(get_current_active_user),
    use_case: GetChecklists = Depends(get_checklists_use_case),
) -> PageResponse[ChecklistSummaryResult]:
    result = await use_case.execute(actor=actor, query=params.to_query())
    return PageResponse.from_result(result, params)


@router.post("", response_model=ChecklistResponse, status_code=status.HTTP_201_CREATED)
async def create_checklist(
    body: ChecklistCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateChecklist = Depends(get_create_checklist_use_case),
) -> ChecklistResult:
    cmd = CreateChecklistCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)


@router.get("/by-public-id/{public_id}", response_model=ChecklistResponse)
async def read_checklist_by_public_id(
    public_id: UUID,
    actor: User = Depends(get_current_active_user),
    use_case: GetChecklistByPublicId = Depends(get_checklist_by_public_id_use_case),
) -> ChecklistResult:
    return await use_case.execute(actor=actor, public_id=public_id)


@router.get("/{checklist_id}", response_model=ChecklistResponse)
async def read_checklist(
    checklist_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: GetChecklist = Depends(get_checklist_use_case),
) -> ChecklistResult:
    return await use_case.execute(actor=actor, checklist_id=checklist_id)


@router.get("/{checklist_id}/revisions", response_model=list[ChecklistSummaryResponse])
async def read_checklist_revisions(
    checklist_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: GetChecklistRevisions = Depends(get_checklist_revisions_use_case),
) -> list[ChecklistSummaryResult]:
    return await use_case.execute(actor=actor, checklist_id=checklist_id)


@router.put("/{checklist_id}", response_model=ChecklistResponse)
async def update_checklist(
    checklist_id: int,
    body: ChecklistUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateChecklist = Depends(get_update_checklist_use_case),
) -> ChecklistResult:
    cmd = UpdateChecklistCommand(**body.model_dump())
    return await use_case.execute(actor=actor, checklist_id=checklist_id, cmd=cmd)


@router.post(
    "/{checklist_id}/revise",
    response_model=ChecklistResponse,
    status_code=status.HTTP_201_CREATED,
)
async def revise_checklist(
    checklist_id: int,
    body: ChecklistReviseRequest,
    actor: User = Depends(get_current_active_user),
    use_case: ReviseChecklist = Depends(get_revise_checklist_use_case),
) -> ChecklistResult:
    cmd = ReviseChecklistCommand(**body.model_dump())
    return await use_case.execute(actor=actor, checklist_id=checklist_id, cmd=cmd)


@router.post("/{checklist_id}/release", response_model=ChecklistResponse)
async def release_checklist(
    checklist_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: ReleaseChecklist = Depends(get_release_checklist_use_case),
) -> ChecklistResult:
    return await use_case.execute(actor=actor, checklist_id=checklist_id)


@router.post("/{checklist_id}/lock", response_model=ChecklistResponse)
async def lock_checklist(
    checklist_id: int,
    body: DocumentLockRequest,
    actor: User = Depends(get_current_active_user),
    use_case: LockChecklist = Depends(get_lock_checklist_use_case),
) -> ChecklistResult:
    """Takes the edit lock, or renews the lease of the one the caller holds."""
    cmd = LockCommand(**body.model_dump())
    return await use_case.execute(actor=actor, checklist_id=checklist_id, cmd=cmd)


@router.delete("/{checklist_id}/lock", response_model=ChecklistResponse)
async def unlock_checklist(
    checklist_id: int,
    force: bool = Query(
        default=False, description="End another user's editing; needs manage:checklists"
    ),
    actor: User = Depends(get_current_active_user),
    use_case: UnlockChecklist = Depends(get_unlock_checklist_use_case),
) -> ChecklistResult:
    return await use_case.execute(actor=actor, checklist_id=checklist_id, force=force)


@router.post("/{checklist_id}/mark-invalid", response_model=ChecklistResponse)
async def mark_checklist_invalid(
    checklist_id: int,
    body: DocumentReasonRequest,
    actor: User = Depends(get_current_active_user),
    use_case: MarkChecklistInvalid = Depends(get_mark_checklist_invalid_use_case),
) -> ChecklistResult:
    cmd = MarkInvalidCommand(**body.model_dump())
    return await use_case.execute(actor=actor, checklist_id=checklist_id, cmd=cmd)


@router.delete("/{checklist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_checklist(
    checklist_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: DeleteChecklist = Depends(get_delete_checklist_use_case),
) -> None:
    await use_case.execute(actor=actor, checklist_id=checklist_id)
