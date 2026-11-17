"""Domain entity for the cross-cutting general settings singleton."""

from dataclasses import dataclass

from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class AdminGeneralSettings(Entity):
    """Cross-cutting settings that belong to no single module.

    The *_pattern fields validate hand-entered numbers rather than generate
    them; "" means no enforcement.
    """

    # The organisation, as opposed to how the application is branded.
    company_name: str | None  # trading name, e.g. "Example"
    company_legal_name: str | None  # full legal entity, e.g. "Example Ltd"
    company_logo_key: str | None  # storage key, not a URL

    # Contact and legal links for the UI footer and help menus.
    contact_email: str | None
    imprint_url: str | None
    privacy_url: str | None
    support_url: str | None

    product_number_pattern: str
    project_number_pattern: str
    # False means a project must reference a product.
    allow_headless_projects: bool
    # Free text the UI shows for a missing value; never stored in data.
    empty_value_placeholder: str

    # Header link-out popover to the M365 web apps, without SSO.
    office_launcher_enabled: bool
    # "" hides the SharePoint tile. Not nullable, because the update use
    # case reads None as "leave as is" and could never clear it.
    office_sharepoint_url: str

    # ISO 4217 display currency for the whole tenant; prices are stored as
    # integer cents regardless.
    currency: str

    # Defaults for new users and the pre-login screen.
    default_language: Language
    # The one timezone the whole app reads calendar days and wall-clock
    # times in, for every user. Stored instants stay UTC.
    default_timezone: str
    default_date_format: DateFormat
