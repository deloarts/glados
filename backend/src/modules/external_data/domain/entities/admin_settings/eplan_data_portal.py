"""
Domain entity for the EPLAN Data Portal settings singleton: whether the
lookups are on, where the portal's API is, the organisation's personal
access token (encrypted at rest, never returned), the article groups an
item from the portal gets by default, and the language its article name is
taken in.
"""

from dataclasses import dataclass
from dataclasses import field
from urllib.parse import urlsplit

from src.modules.external_data.domain.errors import EdpSettingsInvalidError
from src.modules.external_data.domain.value_objects.eplan_data_portal import EDP_LANGUAGES
from src.shared_kernel.domain.entities.base import Entity

DEFAULT_EDP_BASE_URL = "https://dataportal.eplan.com/api"


def normalize_edp_base_url(value: str) -> str:
    """The API base URL as stored: https only, a host, no user info, query
    or fragment, no trailing slash."""
    trimmed = value.strip().rstrip("/")
    parts = urlsplit(trimmed)
    if parts.scheme.lower() != "https" or not parts.hostname:
        raise EdpSettingsInvalidError("The Data Portal URL must be an https:// address.")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise EdpSettingsInvalidError(
            "The Data Portal URL must not contain user information, a query or a fragment."
        )
    return trimmed


@dataclass
class AdminEdpSettings(Entity):
    enabled: bool = False
    base_url: str = DEFAULT_EDP_BASE_URL
    pat: str | None = field(default=None, repr=False)
    default_article_group_ids: list[int] = field(default_factory=list)
    language: str = "de_DE"

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.pat)

    def assert_valid(self) -> None:
        if self.language not in EDP_LANGUAGES:
            raise EdpSettingsInvalidError(f"Unsupported language {self.language!r}.")
        if self.enabled and not self.pat:
            raise EdpSettingsInvalidError(
                "Enter a personal access token before switching the Data Portal on."
            )
