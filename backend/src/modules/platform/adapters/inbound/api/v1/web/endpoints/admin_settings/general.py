"""
Admin settings endpoints for the Host tab and the General tab (including
the company logo). All reads require read:settings;
all writes require write:settings.
"""

from fastapi import Depends
from fastapi import UploadFile
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_delete_company_logo_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_general_settings_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.admin_settings import get_host_settings_use_case
from src.modules.platform.adapters.inbound.api.deps.admin_settings import get_host_stats_use_case
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_services_health_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_update_general_settings_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_upload_company_logo_use_case,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.general import (
    AdminGeneralSettingsResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.general import (
    UpdateGeneralSettingsRequest,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.host import (
    AdminHostSettingsResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.host import (
    HostStatsResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.host import (
    ServicesHealthResponse,
)
from src.modules.platform.adapters.inbound.api.upload_limits import max_upload_size
from src.modules.platform.application.dto.admin_settings_dto.general import (
    AdminGeneralSettingsResult,
)
from src.modules.platform.application.dto.admin_settings_dto.general import (
    UpdateGeneralSettingsCommand,
)
from src.modules.platform.application.dto.admin_settings_dto.host import AdminHostSettingsResult
from src.modules.platform.application.dto.admin_settings_dto.host import HostStatsResult
from src.modules.platform.application.dto.admin_settings_dto.host import ServicesHealthResult
from src.modules.platform.application.use_cases.admin_settings.delete_company_logo import (
    DeleteCompanyLogo,
)
from src.modules.platform.application.use_cases.admin_settings.get_general_settings import (
    GetGeneralSettings,
)
from src.modules.platform.application.use_cases.admin_settings.get_host_settings import (
    GetHostSettings,
)
from src.modules.platform.application.use_cases.admin_settings.get_host_stats import GetHostStats
from src.modules.platform.application.use_cases.admin_settings.get_services_health import (
    GetServicesHealth,
)
from src.modules.platform.application.use_cases.admin_settings.update_general_settings import (
    UpdateGeneralSettings,
)
from src.modules.platform.application.use_cases.admin_settings.upload_company_logo import (
    MAX_BYTES as COMPANY_LOGO_MAX_BYTES,
)
from src.modules.platform.application.use_cases.admin_settings.upload_company_logo import (
    UploadCompanyLogo,
)
from src.modules.platform.domain.entities.user import User

router = APIRouter()


# ── Host ──────────────────────────────────────────────────────────────


@router.get("/host", response_model=AdminHostSettingsResponse)
async def get_host_settings(
    actor: User = Depends(get_current_active_user),
    use_case: GetHostSettings = Depends(get_host_settings_use_case),
) -> AdminHostSettingsResult:
    return await use_case.execute(actor=actor)


# No PUT /host: the domain has no stored fields. The contact address and
# legal URLs live under /general, and the Host tab shows
# live machine statistics, which are read rather than configured.


@router.get("/host/stats", response_model=HostStatsResponse)
async def get_host_stats(
    actor: User = Depends(get_current_active_user),
    use_case: GetHostStats = Depends(get_host_stats_use_case),
) -> HostStatsResult:
    """Live CPU / memory / disk figures for the Host tab. Requires read:settings.

    Deliberately not part of GET /admin/settings/: that aggregate is fetched
    once when the settings screen opens, whereas this is polled every few
    seconds, and a reading is only meaningful at the moment it is taken.
    """
    return await use_case.execute(actor=actor)


@router.get("/host/services", response_model=ServicesHealthResponse)
async def get_services_health(
    actor: User = Depends(get_current_active_user),
    use_case: GetServicesHealth = Depends(get_services_health_use_case),
) -> ServicesHealthResult:
    """Live connectivity status of Postgres, Redis, and the configured
    storage backend, for the Host tab's service panel. Requires read:settings.

    Deliberately not part of GET /admin/settings/, same reasoning as
    /host/stats: polled every few seconds, so a reading is only meaningful
    at the moment it is taken.
    """
    return await use_case.execute(actor=actor)


# ── General ───────────────────────────────────────────────────────────


@router.get("/general", response_model=AdminGeneralSettingsResponse)
async def get_general_settings(
    actor: User = Depends(get_current_active_user),
    use_case: GetGeneralSettings = Depends(get_general_settings_use_case),
) -> AdminGeneralSettingsResult:
    return await use_case.execute(actor=actor)


@router.put("/general", response_model=AdminGeneralSettingsResponse)
async def update_general_settings(
    body: UpdateGeneralSettingsRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateGeneralSettings = Depends(get_update_general_settings_use_case),
) -> AdminGeneralSettingsResult:
    """Update cross-cutting settings. Partial, omitted fields keep their current
    value, because the Numbering and General tabs each write a subset. Requires
    write:settings.
    """
    cmd = UpdateGeneralSettingsCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)


@router.post(
    "/general/company-logo",
    response_model=AdminGeneralSettingsResponse,
    dependencies=[Depends(max_upload_size(COMPANY_LOGO_MAX_BYTES))],
)
async def upload_company_logo(
    file: UploadFile,
    actor: User = Depends(get_current_active_user),
    use_case: UploadCompanyLogo = Depends(get_upload_company_logo_use_case),
) -> AdminGeneralSettingsResult:
    """Upload or replace the company logo (PNG/JPEG/SVG/WebP, ≤ 5 MB).

    Requires write:settings.
    """
    data = await file.read()
    return await use_case.execute(actor=actor, data=data, content_type=file.content_type or "")


@router.delete("/general/company-logo", response_model=AdminGeneralSettingsResponse)
async def delete_company_logo(
    actor: User = Depends(get_current_active_user),
    use_case: DeleteCompanyLogo = Depends(get_delete_company_logo_use_case),
) -> AdminGeneralSettingsResult:
    """Remove the company logo. Requires write:settings."""
    return await use_case.execute(actor=actor)
