"""
Saved calculations of the engineering tools under /tools. Every route only
requires login; permissions are checked in the use cases (see
CalculationRules).
"""

from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query
from fastapi import status

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.user import User
from src.modules.quality.adapters.inbound.api.deps.calculations import (
    get_calculation_by_public_id_use_case,
)
from src.modules.quality.adapters.inbound.api.deps.calculations import (
    get_calculation_revisions_use_case,
)
from src.modules.quality.adapters.inbound.api.deps.calculations import get_calculation_use_case
from src.modules.quality.adapters.inbound.api.deps.calculations import get_calculations_use_case
from src.modules.quality.adapters.inbound.api.deps.calculations import (
    get_create_calculation_use_case,
)
from src.modules.quality.adapters.inbound.api.deps.calculations import (
    get_delete_calculation_use_case,
)
from src.modules.quality.adapters.inbound.api.deps.calculations import get_lock_calculation_use_case
from src.modules.quality.adapters.inbound.api.deps.calculations import (
    get_mark_calculation_invalid_use_case,
)
from src.modules.quality.adapters.inbound.api.deps.calculations import (
    get_release_calculation_use_case,
)
from src.modules.quality.adapters.inbound.api.deps.calculations import (
    get_revise_calculation_use_case,
)
from src.modules.quality.adapters.inbound.api.deps.calculations import (
    get_set_calculation_device_use_case,
)
from src.modules.quality.adapters.inbound.api.deps.calculations import (
    get_unlock_calculation_use_case,
)
from src.modules.quality.adapters.inbound.api.deps.calculations import (
    get_update_calculation_use_case,
)
from src.modules.quality.adapters.inbound.api.schemas.calculation_schema import (
    CalculationCreateRequest,
)
from src.modules.quality.adapters.inbound.api.schemas.calculation_schema import (
    CalculationDeviceRequest,
)
from src.modules.quality.adapters.inbound.api.schemas.calculation_schema import (
    CalculationFilterParams,
)
from src.modules.quality.adapters.inbound.api.schemas.calculation_schema import CalculationResponse
from src.modules.quality.adapters.inbound.api.schemas.calculation_schema import (
    CalculationReviseRequest,
)
from src.modules.quality.adapters.inbound.api.schemas.calculation_schema import (
    CalculationSummaryResponse,
)
from src.modules.quality.adapters.inbound.api.schemas.calculation_schema import (
    CalculationUpdateRequest,
)
from src.modules.quality.adapters.inbound.api.schemas.controlled_document_schema import (
    DocumentLockRequest,
)
from src.modules.quality.adapters.inbound.api.schemas.controlled_document_schema import (
    DocumentReasonRequest,
)
from src.modules.quality.application.dto.calculation_dto import CalculationResult
from src.modules.quality.application.dto.calculation_dto import CalculationSummaryResult
from src.modules.quality.application.dto.calculation_dto import CreateCalculationCommand
from src.modules.quality.application.dto.calculation_dto import ReviseCalculationCommand
from src.modules.quality.application.dto.calculation_dto import UpdateCalculationCommand
from src.modules.quality.application.dto.controlled_document_dto import LockCommand
from src.modules.quality.application.dto.controlled_document_dto import MarkInvalidCommand
from src.modules.quality.application.use_cases.calculation.delete_calculation import (
    DeleteCalculation,
)
from src.modules.quality.application.use_cases.calculation.get_calculations import GetCalculation
from src.modules.quality.application.use_cases.calculation.get_calculations import (
    GetCalculationByPublicId,
)
from src.modules.quality.application.use_cases.calculation.get_calculations import (
    GetCalculationRevisions,
)
from src.modules.quality.application.use_cases.calculation.get_calculations import GetCalculations
from src.modules.quality.application.use_cases.calculation.lock_calculation import LockCalculation
from src.modules.quality.application.use_cases.calculation.lock_calculation import UnlockCalculation
from src.modules.quality.application.use_cases.calculation.release_calculation import (
    MarkCalculationInvalid,
)
from src.modules.quality.application.use_cases.calculation.release_calculation import (
    ReleaseCalculation,
)
from src.modules.quality.application.use_cases.calculation.revise_calculation import (
    ReviseCalculation,
)
from src.modules.quality.application.use_cases.calculation.save_calculation import CreateCalculation
from src.modules.quality.application.use_cases.calculation.save_calculation import (
    SetCalculationDevice,
)
from src.modules.quality.application.use_cases.calculation.save_calculation import UpdateCalculation

router = APIRouter()


@router.get("", response_model=PageResponse[CalculationSummaryResponse])
async def read_calculations(
    params: CalculationFilterParams = Depends(),
    actor: User = Depends(get_current_active_user),
    use_case: GetCalculations = Depends(get_calculations_use_case),
) -> PageResponse[CalculationSummaryResult]:
    result = await use_case.execute(actor=actor, query=params.to_query())
    return PageResponse.from_result(result, params)


@router.post("", response_model=CalculationResponse, status_code=status.HTTP_201_CREATED)
async def create_calculation(
    body: CalculationCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateCalculation = Depends(get_create_calculation_use_case),
) -> CalculationResult:
    cmd = CreateCalculationCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)


@router.get("/by-public-id/{public_id}", response_model=CalculationResponse)
async def read_calculation_by_public_id(
    public_id: UUID,
    actor: User = Depends(get_current_active_user),
    use_case: GetCalculationByPublicId = Depends(get_calculation_by_public_id_use_case),
) -> CalculationResult:
    return await use_case.execute(actor=actor, public_id=public_id)


@router.get("/{calculation_id}", response_model=CalculationResponse)
async def read_calculation(
    calculation_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: GetCalculation = Depends(get_calculation_use_case),
) -> CalculationResult:
    return await use_case.execute(actor=actor, calculation_id=calculation_id)


@router.get("/{calculation_id}/revisions", response_model=list[CalculationSummaryResponse])
async def read_calculation_revisions(
    calculation_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: GetCalculationRevisions = Depends(get_calculation_revisions_use_case),
) -> list[CalculationSummaryResult]:
    return await use_case.execute(actor=actor, calculation_id=calculation_id)


@router.put("/{calculation_id}", response_model=CalculationResponse)
async def update_calculation(
    calculation_id: int,
    body: CalculationUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateCalculation = Depends(get_update_calculation_use_case),
) -> CalculationResult:
    cmd = UpdateCalculationCommand(**body.model_dump())
    return await use_case.execute(actor=actor, calculation_id=calculation_id, cmd=cmd)


@router.put("/{calculation_id}/device", response_model=CalculationResponse)
async def set_calculation_device(
    calculation_id: int,
    body: CalculationDeviceRequest,
    actor: User = Depends(get_current_active_user),
    use_case: SetCalculationDevice = Depends(get_set_calculation_device_use_case),
) -> CalculationResult:
    """Links a draft to a device of its product, or with null unlinks it."""
    return await use_case.execute(
        actor=actor, calculation_id=calculation_id, device_id=body.product_device_id
    )


@router.post(
    "/{calculation_id}/revise",
    response_model=CalculationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def revise_calculation(
    calculation_id: int,
    body: CalculationReviseRequest,
    actor: User = Depends(get_current_active_user),
    use_case: ReviseCalculation = Depends(get_revise_calculation_use_case),
) -> CalculationResult:
    cmd = ReviseCalculationCommand(**body.model_dump())
    return await use_case.execute(actor=actor, calculation_id=calculation_id, cmd=cmd)


@router.post("/{calculation_id}/release", response_model=CalculationResponse)
async def release_calculation(
    calculation_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: ReleaseCalculation = Depends(get_release_calculation_use_case),
) -> CalculationResult:
    return await use_case.execute(actor=actor, calculation_id=calculation_id)


@router.post("/{calculation_id}/lock", response_model=CalculationResponse)
async def lock_calculation(
    calculation_id: int,
    body: DocumentLockRequest,
    actor: User = Depends(get_current_active_user),
    use_case: LockCalculation = Depends(get_lock_calculation_use_case),
) -> CalculationResult:
    """Takes the edit lock, or renews the lease of the one the caller holds."""
    cmd = LockCommand(**body.model_dump())
    return await use_case.execute(actor=actor, calculation_id=calculation_id, cmd=cmd)


@router.delete("/{calculation_id}/lock", response_model=CalculationResponse)
async def unlock_calculation(
    calculation_id: int,
    force: bool = Query(
        default=False, description="End another user's editing; needs manage:calculations"
    ),
    actor: User = Depends(get_current_active_user),
    use_case: UnlockCalculation = Depends(get_unlock_calculation_use_case),
) -> CalculationResult:
    return await use_case.execute(actor=actor, calculation_id=calculation_id, force=force)


@router.post("/{calculation_id}/mark-invalid", response_model=CalculationResponse)
async def mark_calculation_invalid(
    calculation_id: int,
    body: DocumentReasonRequest,
    actor: User = Depends(get_current_active_user),
    use_case: MarkCalculationInvalid = Depends(get_mark_calculation_invalid_use_case),
) -> CalculationResult:
    cmd = MarkInvalidCommand(**body.model_dump())
    return await use_case.execute(actor=actor, calculation_id=calculation_id, cmd=cmd)


@router.delete("/{calculation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_calculation(
    calculation_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: DeleteCalculation = Depends(get_delete_calculation_use_case),
) -> None:
    await use_case.execute(actor=actor, calculation_id=calculation_id)
