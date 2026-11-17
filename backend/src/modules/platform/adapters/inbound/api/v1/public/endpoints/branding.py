"""
Unauthenticated branding endpoints, used by the login screen, which has no
token yet. Expose only what's safe to show before authentication.
"""

from fastapi import Depends
from fastapi import Response
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_login_background_video_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_web_app_manifest_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.adapters.inbound.api.deps.repositories import get_platform_settings_repo
from src.modules.platform.adapters.inbound.api.deps.services import get_optional_storage_adapter
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.platform.application.use_cases.admin_settings.get_login_background_video import (
    GetLoginBackgroundVideo,
)
from src.modules.platform.application.use_cases.admin_settings.get_web_app_manifest import (
    GetWebAppManifest,
)
from src.modules.platform.domain.exceptions import BrandingImageNotFoundError
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.infrastructure.config.settings import cfg
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork

router = APIRouter()


class PublicBrandingResponse(ResponseModel):
    app_name: str
    # Shown as a tagline under the app name in the header; null when the
    # admin left it blank so the shell renders nothing rather than "".
    app_description: str | None
    footer_text: str | None
    # From the general settings domain, not branding: the footer shows it on
    # every page including the login screen, which has no token, so it has to
    # travel on the one branding call the shell already makes.
    company_name: str | None
    # Also from the general settings domain ("Contact & Legal"): the footer
    # renders them as Contact | Support | Imprint | Privacy links next to the
    # company name, on every page including the login screen.
    contact_email: str | None
    support_url: str | None
    imprint_url: str | None
    privacy_url: str | None
    has_logo: bool
    # The company's own mark from the general settings, distinct from the
    # branding logo; reports the browser renders put it in their header.
    has_company_logo: bool
    has_favicon: bool
    has_login_background_video: bool
    # The tenant's configured default language: the login screen has no
    # token and no user yet, so this is the only place it can learn which
    # language to render in before anyone signs in.
    default_language: Language
    # Maintenance mode: the login screen has no token either, so this is
    # the only way it can show the notice before a 503 from an actual
    # login attempt would otherwise be the first sign of it.
    maintenance_enabled: bool
    maintenance_message: str | None
    # The address the app is served at, from the deployment configuration.
    # QR codes on reports point to its resolve page, the same links labels
    # print, so a code works whichever host the exporting browser used.
    domain: str


@router.get("/branding", response_model=PublicBrandingResponse)
async def get_public_branding(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
) -> PublicBrandingResponse:
    """Return the branding fields needed to render the (pre-auth) login screen."""
    branding = await repo.get_branding()
    general = await repo.get_general()
    maintenance = await repo.get_maintenance()
    return PublicBrandingResponse(
        app_name=branding.app_name,
        app_description=branding.app_description,
        footer_text=branding.footer_text,
        company_name=general.company_name,
        contact_email=general.contact_email,
        support_url=general.support_url,
        imprint_url=general.imprint_url,
        privacy_url=general.privacy_url,
        has_logo=branding.logo_key is not None,
        has_company_logo=general.company_logo_key is not None,
        has_favicon=branding.favicon_key is not None,
        has_login_background_video=branding.login_background_video_key is not None,
        default_language=general.default_language,
        maintenance_enabled=maintenance.enabled,
        maintenance_message=maintenance.message,
        domain=cfg.domain,
    )


@router.get("/branding/logo")
async def get_public_logo(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> Response:
    """Stream the branding logo bytes. No auth required."""
    branding = await repo.get_branding()
    if not branding.logo_key or storage is None:
        raise BrandingImageNotFoundError("No branding logo is configured.")
    await uow.commit()  # free the connection for the storage read
    data, content_type = await storage.download(branding.logo_key)
    return Response(
        content=data, media_type=content_type, headers={"Cache-Control": "public, max-age=3600"}
    )


@router.get("/company/logo")
async def get_public_company_logo(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> Response:
    """Stream the company logo bytes. No auth required.

    Public for the same reason the branding logo is: it is shown before a token
    exists, and a company's own mark is not sensitive.
    """
    general = await repo.get_general()
    if not general.company_logo_key or storage is None:
        raise BrandingImageNotFoundError("No company logo is configured.")
    await uow.commit()  # free the connection for the storage read
    data, content_type = await storage.download(general.company_logo_key)
    return Response(
        content=data, media_type=content_type, headers={"Cache-Control": "public, max-age=3600"}
    )


@router.get("/branding/favicon")
async def get_public_favicon(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> Response:
    """Stream the branding favicon bytes. No auth required."""
    branding = await repo.get_branding()
    if not branding.favicon_key or storage is None:
        raise BrandingImageNotFoundError("No branding favicon is configured.")
    await uow.commit()  # free the connection for the storage read
    data, content_type = await storage.download(branding.favicon_key)
    return Response(
        content=data, media_type=content_type, headers={"Cache-Control": "public, max-age=3600"}
    )


@router.get("/branding/login-video")
async def get_public_login_background_video(
    use_case: GetLoginBackgroundVideo = Depends(get_login_background_video_use_case),
) -> Response:
    """Stream the login screen's background video bytes. No auth required."""
    data, content_type = await use_case.execute()
    return Response(
        content=data, media_type=content_type, headers={"Cache-Control": "public, max-age=3600"}
    )


class WebAppManifestJSONResponse(JSONResponse):
    media_type = "application/manifest+json"


class WebAppManifestIconResponse(ResponseModel):
    src: str
    sizes: str
    type: str


class WebAppManifestResponse(ResponseModel):
    id: str
    name: str
    short_name: str
    description: str | None
    start_url: str
    scope: str
    display: str
    background_color: str
    theme_color: str
    icons: list[WebAppManifestIconResponse]


# The Glados icons the frontend serves from its public folder, for an
# installation whose favicon is too small or no image a launcher can scale.
_FALLBACK_ICONS = [
    WebAppManifestIconResponse(src="/icons/glados-192.png", sizes="192x192", type="image/png"),
    WebAppManifestIconResponse(src="/icons/glados-512.png", sizes="512x512", type="image/png"),
]
# The default primary colour, the same as the theme-color in index.html.
_THEME_COLOR = "#007acc"


@router.get(
    "/branding/manifest.webmanifest",
    response_model=WebAppManifestResponse,
    response_model_exclude_none=True,
    response_class=WebAppManifestJSONResponse,
)
async def get_web_app_manifest(
    response: Response,
    use_case: GetWebAppManifest = Depends(get_web_app_manifest_use_case),
) -> WebAppManifestResponse:
    """The web app manifest that lets a phone or a desktop install Glados.

    Its name and description come from the branding settings, and its icon is
    the branding favicon when that is large enough, otherwise the Glados icon.
    The app is served from this origin, so every address is a path.
    """
    manifest = await use_case.execute()
    icons = (
        [
            WebAppManifestIconResponse(
                src="/api/v1/public/branding/favicon",
                sizes=manifest.favicon_sizes,
                type=manifest.favicon_type,
            )
        ]
        if manifest.favicon_type is not None and manifest.favicon_sizes is not None
        else _FALLBACK_ICONS
    )
    response.headers["Cache-Control"] = "public, max-age=3600"
    return WebAppManifestResponse(
        id="/",
        name=manifest.name,
        short_name=manifest.name,
        description=manifest.description,
        start_url="/",
        scope="/",
        display="standalone",
        background_color="#ffffff",
        theme_color=_THEME_COLOR,
        icons=icons,
    )
