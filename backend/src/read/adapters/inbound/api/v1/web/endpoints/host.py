"""Host-level endpoints any signed-in user can call, regardless of
read:settings: backend version, static dropdown value lists, instance-wide
feature flags and presentation defaults, and made/bought part-numbering
policy. These back the frontend's hostStore so every client can render
itself correctly (navigation, forms, numbering previews) without needing
admin-settings access.
"""

from typing import Literal

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.supplier_level import SupplierLevel
from src.modules.external_data.application.facade.pdm_status import is_pdm_enabled
from src.modules.operations.application.facade.time_tracking_status import (
    is_time_tracking_available,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.platform.application.services.tenant_timezone import tenant_zone
from src.modules.platform.const import NAME
from src.modules.platform.const import VERSION
from src.modules.platform.domain.entities.admin_settings.agents import AdminAgentSettings
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.agent_policy import agent_token_lifetime_cap
from src.modules.platform.domain.services.numbering_format import render_example
from src.modules.platform.domain.services.token_permission_rules import AGENT_DRAFT_SCOPES
from src.modules.platform.domain.services.token_permission_rules import AGENT_READ_SCOPES
from src.modules.platform.domain.services.token_permission_rules import PDM_ADDIN_SCOPES
from src.modules.platform.domain.services.token_permission_rules import SOLIDWORKS_ADDIN_SCOPES
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.start_page import StartPage
from src.modules.platform.domain.value_objects.theme import ThemePreset
from src.modules.platform.domain.value_objects.theme import ThemePrimary
from src.modules.platform.domain.value_objects.theme import ThemeSurface
from src.modules.platform.domain.value_objects.timezone import Timezone
from src.read.adapters.inbound.api.deps import get_admin_settings_repo
from src.read.ports.outbound.repositories.admin_settings_repository import IAdminSettingsRepository
from src.shared_kernel.domain.services.clock import today_in

router = APIRouter()


@router.get("/version")
async def get_version(_: User = Depends(get_current_active_user)) -> dict[str, str]:
    """Return the current application version."""
    return {"name": NAME, "version": VERSION}


class ValuesResponse(ResponseModel):
    languages: list[Language]
    # Not an enum like the rest, the platform's tz database, sorted.
    timezones: list[str]
    date_formats: list[DateFormat]
    theme_presets: list[ThemePreset]
    theme_surfaces: list[ThemeSurface]
    theme_primaries: list[ThemePrimary]
    supplier_levels: list[SupplierLevel]
    start_pages: list[StartPage]


@router.get("/values", response_model=ValuesResponse)
async def get_values(_: User = Depends(get_current_active_user)) -> ValuesResponse:
    """Return all valid enumerated values the frontend needs to bootstrap dropdowns."""
    return ValuesResponse(
        languages=list(Language),
        timezones=Timezone.values(),
        date_formats=list(DateFormat),
        theme_presets=list(ThemePreset),
        theme_surfaces=list(ThemeSurface),
        theme_primaries=list(ThemePrimary),
        supplier_levels=list(SupplierLevel),
        start_pages=list(StartPage),
    )


class FeatureFlags(ResponseModel):
    production_planning: bool
    # The optional modules an admin can switch off; off hides them from
    # navigation, tabs and the buttons that lead into them.
    calculations: bool = True
    checklists: bool = True
    devices: bool = True
    sequences: bool = True
    todos: bool = True
    # Time tracking is enabled, its service set up and its key confirmed.
    time_tracking: bool
    # The EPLAN Data Portal lookups are switched on and have a token.
    eplan_data_portal: bool = False
    # The name of the time tracking system, as the service reported it when
    # its key was confirmed, so labels can name it; None while time tracking
    # is off.
    time_tracking_provider_label: str | None


class ServerCapabilities(ResponseModel):
    storage_enabled: bool
    mail_enabled: bool
    # The total size the attachments of one composed mail may reach, so a
    # compose dialog can leave out the files that would not fit before it
    # sends.
    mail_attachment_limit_mb: int
    features: FeatureFlags
    # Presentation data from the general settings, not feature switches.
    empty_value_placeholder: str
    office_launcher_enabled: bool
    office_sharepoint_url: str
    # Locale defaults, needed before a user's own preference is known.
    default_language: Language
    default_timezone: str
    default_date_format: DateFormat
    currency: str
    # Any user may create a PAT, so the create dialog needs the cap.
    token_max_lifetime_days: int
    # Scopes the add-in token shortcuts pre-fill, so the frontend never
    # hardcodes them.
    addin_scopes: list[str]
    pdm_addin_scopes: list[str]
    # Whether AI agents may connect (/api/v1/mcp), the lifetime cap of an
    # agent token, which is never lifted, and the scopes of the two agent
    # token presets.
    agent_access_enabled: bool
    agent_token_max_lifetime_days: int
    agent_read_scopes: list[str]
    agent_draft_scopes: list[str]
    # Only exempt users reach this during maintenance; the banner reminds
    # them the switch is still on.
    maintenance_enabled: bool
    maintenance_message: str | None


@router.get("/capabilities", response_model=ServerCapabilities)
async def get_server_capabilities(
    _: User = Depends(get_current_active_user),
    repo: IAdminSettingsRepository = Depends(get_admin_settings_repo),
) -> ServerCapabilities:
    """Return which optional services are active, which feature modules are
    switched on, and general-domain presentation settings (empty-value
    placeholder, office launcher, locale defaults).

    Any authenticated user may call this. The feature flags and the general
    settings below live here rather than under /admin/settings/ because every
    user's UI needs them to decide what to render (the header waffle button
    included), and reading /admin/settings/ requires read:settings. Nothing
    here is sensitive, a user can already tell which modules exist by looking
    at the navigation.
    """
    features = await repo.get_features()
    time_tracking_settings = await repo.get_time_tracking()
    time_tracking = is_time_tracking_available(time_tracking_settings)
    edp = await repo.get_edp()
    general = await repo.get_general()
    maintenance = await repo.get_maintenance()
    security = await repo.get_security()
    try:
        agents = await repo.get_agents()
    except RuntimeError:
        # Seeded on every start; only a database that never ran the seed
        # lacks the row, and there agent access counts as off.
        agents = AdminAgentSettings(id=1)
    storage = await repo.get_storage()
    mail = await repo.get_mail()
    return ServerCapabilities(
        storage_enabled=storage.enabled,
        mail_enabled=mail.enabled,
        mail_attachment_limit_mb=mail.attachment_limit_mb,
        features=FeatureFlags(
            production_planning=features.enable_production_planning,
            calculations=features.enable_calculations,
            checklists=features.enable_checklists,
            devices=features.enable_devices,
            # A sequence is built from a product's devices, so it goes with them.
            sequences=features.enable_sequences and features.enable_devices,
            todos=features.enable_todos,
            time_tracking=time_tracking,
            eplan_data_portal=edp.enabled and edp.is_configured,
            time_tracking_provider_label=(
                time_tracking_settings.provider_label if time_tracking else None
            ),
        ),
        empty_value_placeholder=general.empty_value_placeholder,
        office_launcher_enabled=general.office_launcher_enabled,
        office_sharepoint_url=general.office_sharepoint_url,
        default_language=general.default_language,
        default_timezone=general.default_timezone,
        default_date_format=general.default_date_format,
        currency=general.currency,
        token_max_lifetime_days=security.token_max_lifetime_days,
        addin_scopes=list(SOLIDWORKS_ADDIN_SCOPES),
        pdm_addin_scopes=list(PDM_ADDIN_SCOPES),
        agent_access_enabled=agents.is_ready,
        agent_token_max_lifetime_days=agent_token_lifetime_cap(
            security.token_max_lifetime_days, agents.token_max_lifetime_days
        ),
        agent_read_scopes=list(AGENT_READ_SCOPES),
        agent_draft_scopes=list(AGENT_DRAFT_SCOPES),
        maintenance_enabled=maintenance.enabled,
        maintenance_message=maintenance.message,
    )


class PartNumberPolicy(ResponseModel):
    auto: bool
    editable: bool
    # Always "internal" today.
    source: Literal["internal", "external"]
    example: str  # rendered preview of the format, e.g. "PUR-26-00001"
    # Already resolved against whether PDM is enabled.
    web_creation_allowed: bool
    # For client hints only; the server decides.
    external_pattern: str


class RevisionFieldPolicyEntry(ResponseModel):
    """Whether a change to `field` on a web item needs a new revision."""

    field: str
    web_requires_revision: bool


class RevisionPolicy(ResponseModel):
    start: str
    separator: str
    skip_ambiguous_letters: bool
    only_newest_editable: bool
    predecessor_status_web: Literal["ask"] | MadeItemCatalogueStatus
    field_policy: list[RevisionFieldPolicyEntry]


class MadeItemPartNumberPolicy(PartNumberPolicy):
    revision: RevisionPolicy


class NumberingPolicy(ResponseModel):
    bought_items: PartNumberPolicy
    made_items: MadeItemPartNumberPolicy
    # Validation regexes for hand-entered numbers; "" means no enforcement.
    # Sent so the project/product forms can reject a bad number before the
    # round-trip; the server still enforces them on create/update.
    product_number_pattern: str
    project_number_pattern: str
    # False = the project form must require a product.
    allow_headless_projects: bool
    # Forms disable PDM-owned inputs on CAD rows when enforced; the server
    # stays authoritative.
    pdm_enabled: bool
    cad_items_read_only: bool


@router.get("/numbering", response_model=NumberingPolicy)
async def get_numbering_policy(
    _: User = Depends(get_current_active_user),
    repo: IAdminSettingsRepository = Depends(get_admin_settings_repo),
) -> NumberingPolicy:
    """Return how part numbers are assigned, so item forms can present the matching
    input state. The rules themselves are enforced server-side on create/update,
    this is presentation data. Any authenticated user may call this; unlike
    /admin/settings/ it exposes no formats a non-admin could not already infer.
    """
    today = today_in(await tenant_zone(repo))
    orders = await repo.get_orders()
    made_items = await repo.get_made_items()
    general = await repo.get_general()
    pdm_settings = await repo.get_pdm()
    pdm_enabled = is_pdm_enabled(pdm_settings)
    return NumberingPolicy(
        product_number_pattern=general.product_number_pattern,
        project_number_pattern=general.project_number_pattern,
        allow_headless_projects=general.allow_headless_projects,
        pdm_enabled=pdm_enabled,
        cad_items_read_only=pdm_settings.cad_items_read_only,
        bought_items=PartNumberPolicy(
            auto=orders.part_number_auto,
            editable=orders.part_number_editable,
            source="internal",
            example=render_example(orders.part_number_format, today=today),
            web_creation_allowed=orders.web_creation_allowed or not pdm_enabled,
            external_pattern=orders.pdm_part_number_pattern,
        ),
        made_items=MadeItemPartNumberPolicy(
            auto=made_items.part_number_auto,
            editable=made_items.part_number_editable,
            source="internal",
            example=render_example(made_items.item_number_format, today=today),
            web_creation_allowed=made_items.web_creation_allowed or not pdm_enabled,
            external_pattern=made_items.pdm_part_number_pattern,
            revision=RevisionPolicy(
                start=made_items.revision_start,
                separator=made_items.revision_separator,
                skip_ambiguous_letters=made_items.revision_skip_ambiguous_letters,
                only_newest_editable=made_items.revision_only_newest_editable,
                predecessor_status_web=made_items.revision_predecessor_status_web,
                field_policy=[
                    RevisionFieldPolicyEntry(
                        field=entry.field,
                        web_requires_revision=entry.web_requires_revision,
                    )
                    for entry in made_items.revision_field_policy
                ],
            ),
        ),
    )
