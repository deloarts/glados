"""
Self-service management of personal access tokens (PAT). Always scoped to
the acting user's own tokens, there is no cross-user listing endpoint;
managing another user's token (e.g. an admin revoking one) still goes
through the {pat_id} routes, gated by PatRules.assert_can_manage
(write:settings required for anyone other than the owner).
The raw token value is returned exactly once, on creation.
"""

from fastapi import Depends
from fastapi import Query
from fastapi import Request
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.users import get_create_pat_use_case
from src.modules.platform.adapters.inbound.api.deps.users import get_pat_usage_log_use_case
from src.modules.platform.adapters.inbound.api.deps.users import get_pat_use_case
from src.modules.platform.adapters.inbound.api.deps.users import get_pats_use_case
from src.modules.platform.adapters.inbound.api.deps.users import get_revoke_all_pats_use_case
from src.modules.platform.adapters.inbound.api.deps.users import get_revoke_pat_use_case
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.adapters.inbound.api.schemas.pat_schema import CreatedPatResult
from src.modules.platform.adapters.inbound.api.schemas.pat_schema import PatCreateRequest
from src.modules.platform.adapters.inbound.api.schemas.pat_schema import PatFilterParams
from src.modules.platform.adapters.inbound.api.schemas.pat_schema import PatResult
from src.modules.platform.adapters.inbound.api.schemas.pat_schema import PatUsageLogEntryResult
from src.modules.platform.adapters.inbound.api.schemas.pat_schema import RevokeAllPatsResult
from src.modules.platform.adapters.inbound.api.v1.auth.login_responses import client_ip
from src.modules.platform.application.dto.pat_dto import CreatePatCommand
from src.modules.platform.application.use_cases.pat.create_pat import CreatePatWithPassword
from src.modules.platform.application.use_cases.pat.get_pat import GetPat
from src.modules.platform.application.use_cases.pat.get_pat import GetPats
from src.modules.platform.application.use_cases.pat.get_pat_usage_log import GetPatUsageLog
from src.modules.platform.application.use_cases.pat.revoke_all_pats import RevokeAllPats
from src.modules.platform.application.use_cases.pat.revoke_pat import RevokePat
from src.modules.platform.const import MAX_PAGE_SIZE
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.repositories.pat_usage_log_repository import (
    PatUsageLogFilterDto,
)

router = APIRouter()


@router.get("/", response_model=PageResponse[PatResult])
async def read_pats(
    params: PatFilterParams = Depends(),
    actor: User = Depends(get_current_active_user),
    use_case: GetPats = Depends(get_pats_use_case),
) -> PageResponse[PatResult]:
    result = await use_case.execute(actor=actor, filters=params.to_dto())
    return PageResponse.from_result(result, params)


@router.post("/", response_model=CreatedPatResult, status_code=status.HTTP_201_CREATED)
async def create_pat(
    body: PatCreateRequest,
    request: Request,
    actor: User = Depends(get_current_active_user),
    use_case: CreatePatWithPassword = Depends(get_create_pat_use_case),
) -> CreatedPatResult:
    """Create a token after confirming the current password. A wrong
    password answers 400 PasswordConfirmationFailedError and counts toward
    the login throttle."""
    cmd = CreatePatCommand(**body.model_dump(exclude={"password"}))
    return await use_case.execute(
        actor=actor, cmd=cmd, password=body.password, client_ip=client_ip(request)
    )


@router.post("/revoke-all", response_model=RevokeAllPatsResult)
async def revoke_all_pats(
    actor: User = Depends(get_current_active_user),
    use_case: RevokeAllPats = Depends(get_revoke_all_pats_use_case),
) -> RevokeAllPatsResult:
    return RevokeAllPatsResult(revoked_count=await use_case.execute(actor=actor))


@router.get("/{pat_id}", response_model=PatResult)
async def read_pat(
    pat_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: GetPat = Depends(get_pat_use_case),
) -> PatResult:
    return await use_case.execute(actor=actor, pat_id=pat_id)


@router.post("/{pat_id}/revoke", response_model=PatResult)
async def revoke_pat(
    pat_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: RevokePat = Depends(get_revoke_pat_use_case),
) -> PatResult:
    return await use_case.execute(actor=actor, pat_id=pat_id)


@router.get("/{pat_id}/usage-log", response_model=PageResponse[PatUsageLogEntryResult])
async def read_pat_usage_log(
    pat_id: int,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE),
    actor: User = Depends(get_current_active_user),
    use_case: GetPatUsageLog = Depends(get_pat_usage_log_use_case),
) -> PageResponse[PatUsageLogEntryResult]:
    filters = PatUsageLogFilterDto(skip=skip, limit=limit)
    result = await use_case.execute(actor=actor, pat_id=pat_id, filters=filters)
    return PageResponse(items=result.items, total=result.total, limit=limit, skip=skip)
