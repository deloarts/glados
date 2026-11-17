"""
Flow sequences of products under /sequences. Every route only requires
login; permissions are checked in the use cases (see SequenceRules).
"""

from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query
from fastapi import status

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.user import User
from src.modules.quality.adapters.inbound.api.deps.sequences import get_create_sequence_use_case
from src.modules.quality.adapters.inbound.api.deps.sequences import get_delete_sequence_use_case
from src.modules.quality.adapters.inbound.api.deps.sequences import get_lock_sequence_use_case
from src.modules.quality.adapters.inbound.api.deps.sequences import (
    get_mark_sequence_invalid_use_case,
)
from src.modules.quality.adapters.inbound.api.deps.sequences import get_release_sequence_use_case
from src.modules.quality.adapters.inbound.api.deps.sequences import get_revise_sequence_use_case
from src.modules.quality.adapters.inbound.api.deps.sequences import (
    get_sequence_by_public_id_use_case,
)
from src.modules.quality.adapters.inbound.api.deps.sequences import get_sequence_revisions_use_case
from src.modules.quality.adapters.inbound.api.deps.sequences import get_sequence_use_case
from src.modules.quality.adapters.inbound.api.deps.sequences import get_sequences_use_case
from src.modules.quality.adapters.inbound.api.deps.sequences import get_unlock_sequence_use_case
from src.modules.quality.adapters.inbound.api.deps.sequences import get_update_sequence_use_case
from src.modules.quality.adapters.inbound.api.schemas.controlled_document_schema import (
    DocumentLockRequest,
)
from src.modules.quality.adapters.inbound.api.schemas.controlled_document_schema import (
    DocumentReasonRequest,
)
from src.modules.quality.adapters.inbound.api.schemas.sequence_schema import SequenceCreateRequest
from src.modules.quality.adapters.inbound.api.schemas.sequence_schema import SequenceFilterParams
from src.modules.quality.adapters.inbound.api.schemas.sequence_schema import SequenceResponse
from src.modules.quality.adapters.inbound.api.schemas.sequence_schema import SequenceReviseRequest
from src.modules.quality.adapters.inbound.api.schemas.sequence_schema import SequenceSummaryResponse
from src.modules.quality.adapters.inbound.api.schemas.sequence_schema import SequenceUpdateRequest
from src.modules.quality.application.dto.controlled_document_dto import LockCommand
from src.modules.quality.application.dto.controlled_document_dto import MarkInvalidCommand
from src.modules.quality.application.dto.sequence_dto import CreateSequenceCommand
from src.modules.quality.application.dto.sequence_dto import ReviseSequenceCommand
from src.modules.quality.application.dto.sequence_dto import SequenceResult
from src.modules.quality.application.dto.sequence_dto import SequenceSummaryResult
from src.modules.quality.application.dto.sequence_dto import UpdateSequenceCommand
from src.modules.quality.application.use_cases.sequence.delete_sequence import DeleteSequence
from src.modules.quality.application.use_cases.sequence.get_sequences import GetSequence
from src.modules.quality.application.use_cases.sequence.get_sequences import GetSequenceByPublicId
from src.modules.quality.application.use_cases.sequence.get_sequences import GetSequenceRevisions
from src.modules.quality.application.use_cases.sequence.get_sequences import GetSequences
from src.modules.quality.application.use_cases.sequence.lock_sequence import LockSequence
from src.modules.quality.application.use_cases.sequence.lock_sequence import UnlockSequence
from src.modules.quality.application.use_cases.sequence.release_sequence import MarkSequenceInvalid
from src.modules.quality.application.use_cases.sequence.release_sequence import ReleaseSequence
from src.modules.quality.application.use_cases.sequence.revise_sequence import ReviseSequence
from src.modules.quality.application.use_cases.sequence.save_sequence import CreateSequence
from src.modules.quality.application.use_cases.sequence.save_sequence import UpdateSequence

router = APIRouter()


@router.get("", response_model=PageResponse[SequenceSummaryResponse])
async def read_sequences(
    params: SequenceFilterParams = Depends(),
    actor: User = Depends(get_current_active_user),
    use_case: GetSequences = Depends(get_sequences_use_case),
) -> PageResponse[SequenceSummaryResult]:
    result = await use_case.execute(actor=actor, query=params.to_query())
    return PageResponse.from_result(result, params)


@router.post("", response_model=SequenceResponse, status_code=status.HTTP_201_CREATED)
async def create_sequence(
    body: SequenceCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateSequence = Depends(get_create_sequence_use_case),
) -> SequenceResult:
    cmd = CreateSequenceCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)


@router.get("/by-public-id/{public_id}", response_model=SequenceResponse)
async def read_sequence_by_public_id(
    public_id: UUID,
    actor: User = Depends(get_current_active_user),
    use_case: GetSequenceByPublicId = Depends(get_sequence_by_public_id_use_case),
) -> SequenceResult:
    return await use_case.execute(actor=actor, public_id=public_id)


@router.get("/{sequence_id}", response_model=SequenceResponse)
async def read_sequence(
    sequence_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: GetSequence = Depends(get_sequence_use_case),
) -> SequenceResult:
    return await use_case.execute(actor=actor, sequence_id=sequence_id)


@router.get("/{sequence_id}/revisions", response_model=list[SequenceSummaryResponse])
async def read_sequence_revisions(
    sequence_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: GetSequenceRevisions = Depends(get_sequence_revisions_use_case),
) -> list[SequenceSummaryResult]:
    return await use_case.execute(actor=actor, sequence_id=sequence_id)


@router.put("/{sequence_id}", response_model=SequenceResponse)
async def update_sequence(
    sequence_id: int,
    body: SequenceUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateSequence = Depends(get_update_sequence_use_case),
) -> SequenceResult:
    cmd = UpdateSequenceCommand(**body.model_dump())
    return await use_case.execute(actor=actor, sequence_id=sequence_id, cmd=cmd)


@router.post(
    "/{sequence_id}/revise",
    response_model=SequenceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def revise_sequence(
    sequence_id: int,
    body: SequenceReviseRequest,
    actor: User = Depends(get_current_active_user),
    use_case: ReviseSequence = Depends(get_revise_sequence_use_case),
) -> SequenceResult:
    cmd = ReviseSequenceCommand(**body.model_dump())
    return await use_case.execute(actor=actor, sequence_id=sequence_id, cmd=cmd)


@router.post("/{sequence_id}/release", response_model=SequenceResponse)
async def release_sequence(
    sequence_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: ReleaseSequence = Depends(get_release_sequence_use_case),
) -> SequenceResult:
    return await use_case.execute(actor=actor, sequence_id=sequence_id)


@router.post("/{sequence_id}/lock", response_model=SequenceResponse)
async def lock_sequence(
    sequence_id: int,
    body: DocumentLockRequest,
    actor: User = Depends(get_current_active_user),
    use_case: LockSequence = Depends(get_lock_sequence_use_case),
) -> SequenceResult:
    """Takes the edit lock, or renews the lease of the one the caller holds."""
    cmd = LockCommand(**body.model_dump())
    return await use_case.execute(actor=actor, sequence_id=sequence_id, cmd=cmd)


@router.delete("/{sequence_id}/lock", response_model=SequenceResponse)
async def unlock_sequence(
    sequence_id: int,
    force: bool = Query(
        default=False, description="End another user's editing; needs manage:sequences"
    ),
    actor: User = Depends(get_current_active_user),
    use_case: UnlockSequence = Depends(get_unlock_sequence_use_case),
) -> SequenceResult:
    return await use_case.execute(actor=actor, sequence_id=sequence_id, force=force)


@router.post("/{sequence_id}/mark-invalid", response_model=SequenceResponse)
async def mark_sequence_invalid(
    sequence_id: int,
    body: DocumentReasonRequest,
    actor: User = Depends(get_current_active_user),
    use_case: MarkSequenceInvalid = Depends(get_mark_sequence_invalid_use_case),
) -> SequenceResult:
    cmd = MarkInvalidCommand(**body.model_dump())
    return await use_case.execute(actor=actor, sequence_id=sequence_id, cmd=cmd)


@router.delete("/{sequence_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sequence(
    sequence_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: DeleteSequence = Depends(get_delete_sequence_use_case),
) -> None:
    await use_case.execute(actor=actor, sequence_id=sequence_id)
