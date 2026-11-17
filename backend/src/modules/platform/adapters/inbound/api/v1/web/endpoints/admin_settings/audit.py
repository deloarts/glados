"""
Admin settings endpoint for the Audit tab. Requires read:settings.
"""

from datetime import date

from fastapi import Depends
from fastapi import Query
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_admin_settings_audit_use_case,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.audit import (
    AdminSettingsAuditEntryResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.application.dto.admin_settings_dto.audit import (
    AdminSettingsAuditEntryResult,
)
from src.modules.platform.application.use_cases.admin_settings.get_admin_settings import (
    GetAdminSettingsAudit,
)
from src.modules.platform.const import MAX_PAGE_SIZE
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.platform_settings_repository import (
    AdminSettingsAuditFilterDto,
)

router = APIRouter()


@router.get("/audit", response_model=PageResponse[AdminSettingsAuditEntryResponse])
async def get_settings_audit(
    skip: int | None = Query(default=None, ge=0),
    limit: int | None = Query(default=None, ge=1, le=MAX_PAGE_SIZE),
    settings_domain: str | None = None,
    changed_by: str | None = None,
    changed_by_id: int | None = None,
    summary: str | None = None,
    changed_from: date | None = None,
    changed_to: date | None = None,
    actor: User = Depends(get_current_active_user),
    use_case: GetAdminSettingsAudit = Depends(get_admin_settings_audit_use_case),
) -> PageResponse[AdminSettingsAuditEntryResult]:
    """Return paginated admin settings change history, newest first. `changed_by`
    and `summary` match substrings case-insensitively, `changed_by_id` matches the
    changing user exactly, `changed_from`/`changed_to` are inclusive calendar days.
    Requires read:settings."""
    filters = AdminSettingsAuditFilterDto(
        skip=skip,
        limit=limit,
        settings_domain=settings_domain,
        changed_by=changed_by,
        changed_by_id=changed_by_id,
        summary=summary,
        changed_from=changed_from,
        changed_to=changed_to,
    )
    total, entries = await use_case.execute(actor=actor, filters=filters)
    return PageResponse(
        items=entries,
        total=total,
        limit=limit,
        skip=skip or 0,
    )
