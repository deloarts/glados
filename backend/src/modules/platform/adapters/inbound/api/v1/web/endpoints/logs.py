"""
Web surface log endpoints. Thin by design:
  parse HTTP → call use case → return HTTP response.
"""

from datetime import datetime
from typing import Any

from fastapi import Depends
from fastapi import Query
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.admin import get_log_entries_use_case
from src.modules.platform.adapters.inbound.api.schemas.log_schema import (
    LogEntriesResponse,  # response_model only
)
from src.modules.platform.application.use_cases.log.get_log_entries import GetLogEntries
from src.modules.platform.const import MAX_PAGE_SIZE
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.repositories.log_repository import LogFilterDto

router = APIRouter()


@router.get("/", response_model=LogEntriesResponse)
async def read_log_entries(
    skip: int | None = Query(default=None, ge=0),
    limit: int | None = Query(default=None, ge=1, le=MAX_PAGE_SIZE),
    user_id: int | None = None,
    username_contains: str | None = None,
    status_code: int | None = None,
    level: str | None = None,
    method: str | None = None,
    path_contains: str | None = None,
    message_contains: str | None = None,
    request_id: str | None = None,
    from_timestamp: datetime | None = None,
    to_timestamp: datetime | None = None,
    actor: User = Depends(get_current_active_user),
    use_case: GetLogEntries = Depends(get_log_entries_use_case),
) -> dict[str, Any]:
    """Retrieve audit log entries. Requires read:settings."""
    filters = LogFilterDto(
        skip=skip,
        limit=limit,
        user_id=user_id,
        username_contains=username_contains,
        status_code=status_code,
        level=level,
        method=method,
        path_contains=path_contains,
        message_contains=message_contains,
        request_id=request_id,
        from_timestamp=from_timestamp,
        to_timestamp=to_timestamp,
    )
    total, entries = await use_case.execute(actor=actor, filters=filters)
    return {"total": total, "items": entries}
