"""
Admin settings endpoint for the Security log tab. Requires read:settings.
"""

from datetime import date

from fastapi import Depends
from fastapi import Query
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_list_security_events_use_case,
)
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.adapters.inbound.api.schemas.security_event_schema import (
    SecurityEventResponse,
)
from src.modules.platform.application.dto.security_event_dto import SecurityEventResult
from src.modules.platform.application.use_cases.security_event.list_security_events import (
    ListSecurityEvents,
)
from src.modules.platform.const import MAX_PAGE_SIZE
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventOutcome
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventType
from src.modules.platform.ports.outbound.repositories.security_event_repository import (
    SecurityEventFilterDto,
)

router = APIRouter()


@router.get("/security-events", response_model=PageResponse[SecurityEventResponse])
async def get_security_events(
    skip: int | None = Query(default=None, ge=0),
    limit: int | None = Query(default=None, ge=1, le=MAX_PAGE_SIZE),
    event_type: SecurityEventType | None = None,
    outcome: SecurityEventOutcome | None = None,
    user_id: int | None = None,
    occurred_from: date | None = None,
    occurred_to: date | None = None,
    actor: User = Depends(get_current_active_user),
    use_case: ListSecurityEvents = Depends(get_list_security_events_use_case),
) -> PageResponse[SecurityEventResult]:
    """Return the security log, newest first. `user_id` matches the acting or
    the target user, `occurred_from`/`occurred_to` are inclusive calendar
    days in the tenant's timezone. Requires read:settings."""
    filters = SecurityEventFilterDto(
        skip=skip,
        limit=limit,
        event_type=event_type,
        outcome=outcome,
        user_id=user_id,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
    )
    total, events = await use_case.execute(actor=actor, filters=filters)
    return PageResponse(items=events, total=total, limit=limit, skip=skip or 0)
