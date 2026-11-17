"""
Admin management of API keys (service-account credentials for
non-interactive/hardware clients, see /api/v1/key). Gated by
manage:api_keys throughout, including reads: unlike catalogue data,
a key list (names, grants, who created them) is itself sensitive.
The raw key value is returned exactly once, on creation. Terminal keys are
created by Operations under the same path (terminal_keys.py).
"""

from fastapi import Depends
from fastapi import Query
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.users import get_api_key_usage_log_use_case
from src.modules.platform.adapters.inbound.api.deps.users import get_api_key_use_case
from src.modules.platform.adapters.inbound.api.deps.users import get_api_keys_use_case
from src.modules.platform.adapters.inbound.api.deps.users import get_create_api_key_use_case
from src.modules.platform.adapters.inbound.api.deps.users import get_revoke_all_api_keys_use_case
from src.modules.platform.adapters.inbound.api.deps.users import get_revoke_api_key_use_case
from src.modules.platform.adapters.inbound.api.schemas.api_key_schema import ApiKeyCreateRequest
from src.modules.platform.adapters.inbound.api.schemas.api_key_schema import ApiKeyFilterParams
from src.modules.platform.adapters.inbound.api.schemas.api_key_schema import ApiKeyResult
from src.modules.platform.adapters.inbound.api.schemas.api_key_schema import (
    ApiKeyUsageLogEntryResult,
)
from src.modules.platform.adapters.inbound.api.schemas.api_key_schema import CreatedApiKeyResult
from src.modules.platform.adapters.inbound.api.schemas.api_key_schema import RevokeAllApiKeysResult
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.application.dto.api_key_dto import CreateApiKeyCommand
from src.modules.platform.application.use_cases.api_key.create_api_key import CreateApiKey
from src.modules.platform.application.use_cases.api_key.get_api_key import GetApiKey
from src.modules.platform.application.use_cases.api_key.get_api_key import GetApiKeys
from src.modules.platform.application.use_cases.api_key.get_api_key_usage_log import (
    GetApiKeyUsageLog,
)
from src.modules.platform.application.use_cases.api_key.revoke_all_api_keys import RevokeAllApiKeys
from src.modules.platform.application.use_cases.api_key.revoke_api_key import RevokeApiKey
from src.modules.platform.const import MAX_PAGE_SIZE
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.repositories.api_key_usage_log_repository import (
    ApiKeyUsageLogFilterDto,
)

router = APIRouter()


@router.get("/", response_model=PageResponse[ApiKeyResult])
async def read_api_keys(
    params: ApiKeyFilterParams = Depends(),
    actor: User = Depends(get_current_active_user),
    use_case: GetApiKeys = Depends(get_api_keys_use_case),
) -> PageResponse[ApiKeyResult]:
    result = await use_case.execute(actor=actor, filters=params.to_dto())
    return PageResponse.from_result(result, params)


@router.post("/", response_model=CreatedApiKeyResult, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: ApiKeyCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateApiKey = Depends(get_create_api_key_use_case),
) -> CreatedApiKeyResult:
    cmd = CreateApiKeyCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)


@router.post("/revoke-all", response_model=RevokeAllApiKeysResult)
async def revoke_all_api_keys(
    actor: User = Depends(get_current_active_user),
    use_case: RevokeAllApiKeys = Depends(get_revoke_all_api_keys_use_case),
) -> RevokeAllApiKeysResult:
    return RevokeAllApiKeysResult(revoked_count=await use_case.execute(actor=actor))


@router.get("/{key_id}", response_model=ApiKeyResult)
async def read_api_key(
    key_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: GetApiKey = Depends(get_api_key_use_case),
) -> ApiKeyResult:
    return await use_case.execute(actor=actor, key_id=key_id)


@router.post("/{key_id}/revoke", response_model=ApiKeyResult)
async def revoke_api_key(
    key_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: RevokeApiKey = Depends(get_revoke_api_key_use_case),
) -> ApiKeyResult:
    return await use_case.execute(actor=actor, key_id=key_id)


@router.get("/{key_id}/usage-log", response_model=PageResponse[ApiKeyUsageLogEntryResult])
async def read_api_key_usage_log(
    key_id: int,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE),
    actor: User = Depends(get_current_active_user),
    use_case: GetApiKeyUsageLog = Depends(get_api_key_usage_log_use_case),
) -> PageResponse[ApiKeyUsageLogEntryResult]:
    filters = ApiKeyUsageLogFilterDto(skip=skip, limit=limit)
    result = await use_case.execute(actor=actor, key_id=key_id, filters=filters)
    return PageResponse(items=result.items, total=result.total, limit=limit, skip=skip)
