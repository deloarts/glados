"""
Admin settings endpoints for the Branding tab: white-label settings, the
login background video, the branding logo, and the favicon. All reads
require read:settings; all writes require write:settings.
"""

from fastapi import Depends
from fastapi import UploadFile
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_branding_settings_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_delete_branding_favicon_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_delete_branding_logo_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_delete_login_background_video_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_update_branding_settings_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_upload_branding_favicon_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_upload_branding_logo_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_upload_login_background_video_use_case,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.branding import (
    AdminBrandingSettingsResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.branding import (
    UpdateBrandingSettingsRequest,
)
from src.modules.platform.adapters.inbound.api.upload_limits import max_upload_size
from src.modules.platform.application.dto.admin_settings_dto.branding import (
    AdminBrandingSettingsResult,
)
from src.modules.platform.application.dto.admin_settings_dto.branding import (
    UpdateBrandingSettingsCommand,
)
from src.modules.platform.application.use_cases.admin_settings.delete_branding_favicon import (
    DeleteBrandingFavicon,
)
from src.modules.platform.application.use_cases.admin_settings.delete_branding_logo import (
    DeleteBrandingLogo,
)
from src.modules.platform.application.use_cases.admin_settings.delete_login_background_video import (
    DeleteLoginBackgroundVideo,
)
from src.modules.platform.application.use_cases.admin_settings.get_branding_settings import (
    GetBrandingSettings,
)
from src.modules.platform.application.use_cases.admin_settings.update_branding_settings import (
    UpdateBrandingSettings,
)
from src.modules.platform.application.use_cases.admin_settings.upload_branding_favicon import (
    MAX_BYTES as FAVICON_MAX_BYTES,
)
from src.modules.platform.application.use_cases.admin_settings.upload_branding_favicon import (
    UploadBrandingFavicon,
)
from src.modules.platform.application.use_cases.admin_settings.upload_branding_logo import (
    MAX_BYTES as BRANDING_LOGO_MAX_BYTES,
)
from src.modules.platform.application.use_cases.admin_settings.upload_branding_logo import (
    UploadBrandingLogo,
)
from src.modules.platform.application.use_cases.admin_settings.upload_login_background_video import (
    MAX_BYTES as LOGIN_VIDEO_MAX_BYTES,
)
from src.modules.platform.application.use_cases.admin_settings.upload_login_background_video import (
    UploadLoginBackgroundVideo,
)
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/branding", response_model=AdminBrandingSettingsResponse)
async def get_branding_settings(
    actor: User = Depends(get_current_active_user),
    use_case: GetBrandingSettings = Depends(get_branding_settings_use_case),
) -> AdminBrandingSettingsResult:
    return await use_case.execute(actor=actor)


@router.put("/branding", response_model=AdminBrandingSettingsResponse)
async def update_branding_settings(
    body: UpdateBrandingSettingsRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateBrandingSettings = Depends(get_update_branding_settings_use_case),
) -> AdminBrandingSettingsResult:
    """Update UI branding and white-label settings. Requires write:settings."""
    cmd = UpdateBrandingSettingsCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)


@router.post(
    "/branding/login-video",
    response_model=AdminBrandingSettingsResponse,
    dependencies=[Depends(max_upload_size(LOGIN_VIDEO_MAX_BYTES))],
)
async def upload_login_background_video(
    file: UploadFile,
    actor: User = Depends(get_current_active_user),
    use_case: UploadLoginBackgroundVideo = Depends(get_upload_login_background_video_use_case),
) -> AdminBrandingSettingsResult:
    """Upload or replace the login screen's background video (MP4/WebM, ≤ 50 MB).

    Requires write:settings.
    """
    data = await file.read()
    return await use_case.execute(actor=actor, data=data, content_type=file.content_type or "")


@router.delete("/branding/login-video", response_model=AdminBrandingSettingsResponse)
async def delete_login_background_video(
    actor: User = Depends(get_current_active_user),
    use_case: DeleteLoginBackgroundVideo = Depends(get_delete_login_background_video_use_case),
) -> AdminBrandingSettingsResult:
    """Remove the login screen's background video. Requires write:settings."""
    return await use_case.execute(actor=actor)


@router.post(
    "/branding/logo",
    response_model=AdminBrandingSettingsResponse,
    dependencies=[Depends(max_upload_size(BRANDING_LOGO_MAX_BYTES))],
)
async def upload_branding_logo(
    file: UploadFile,
    actor: User = Depends(get_current_active_user),
    use_case: UploadBrandingLogo = Depends(get_upload_branding_logo_use_case),
) -> AdminBrandingSettingsResult:
    """Upload or replace the branding logo (PNG/JPEG/SVG/WebP, ≤ 5 MB). Requires write:settings."""
    data = await file.read()
    return await use_case.execute(actor=actor, data=data, content_type=file.content_type or "")


@router.delete("/branding/logo", response_model=AdminBrandingSettingsResponse)
async def delete_branding_logo(
    actor: User = Depends(get_current_active_user),
    use_case: DeleteBrandingLogo = Depends(get_delete_branding_logo_use_case),
) -> AdminBrandingSettingsResult:
    """Remove the branding logo. Requires write:settings."""
    return await use_case.execute(actor=actor)


@router.post(
    "/branding/favicon",
    response_model=AdminBrandingSettingsResponse,
    dependencies=[Depends(max_upload_size(FAVICON_MAX_BYTES))],
)
async def upload_branding_favicon(
    file: UploadFile,
    actor: User = Depends(get_current_active_user),
    use_case: UploadBrandingFavicon = Depends(get_upload_branding_favicon_use_case),
) -> AdminBrandingSettingsResult:
    """Upload or replace the favicon (ICO/PNG/SVG, ≤ 2 MB). Requires write:settings."""
    data = await file.read()
    return await use_case.execute(actor=actor, data=data, content_type=file.content_type or "")


@router.delete("/branding/favicon", response_model=AdminBrandingSettingsResponse)
async def delete_branding_favicon(
    actor: User = Depends(get_current_active_user),
    use_case: DeleteBrandingFavicon = Depends(get_delete_branding_favicon_use_case),
) -> AdminBrandingSettingsResult:
    """Remove the branding favicon. Requires write:settings."""
    return await use_case.execute(actor=actor)
