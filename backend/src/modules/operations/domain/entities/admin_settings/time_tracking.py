"""Domain entity for the time tracking settings singleton and the validation
of its values. docs/TIME_TRACKING.md describes every setting.

Glados reaches the time tracking system only through a time tracking
service in the same stack, so the settings name that service, the API key
Glados calls it with, and the credential key the admin confirmed after a
connection test. Plain http is accepted for the service URL: users'
passwords travel sealed for the service's key, and the service publishes
no port outside the stack's network. The URL still must not carry anything
a redirect could abuse (user info, query or fragment).
"""

from dataclasses import dataclass

from src.modules.operations.domain.errors import TimeTrackingNotConfiguredError
from src.shared_kernel.domain.entities.base import Entity
from src.shared_kernel.domain.services.service_url import assert_plain_http_url
from src.shared_kernel.domain.services.service_url import normalize_service_url

__all__ = ["AdminTimeTrackingSettings", "normalize_privacy_policy_url", "normalize_service_url"]


def normalize_privacy_policy_url(value: str | None) -> str | None:
    """The privacy policy link shown in the consent dialog, or None."""
    if value is None or not value.strip():
        return None
    return assert_plain_http_url(value, "privacy_policy_url")


@dataclass
class AdminTimeTrackingSettings(Entity):
    """Time tracking settings singleton. `api_key` is plaintext in memory
    and encrypted at rest; it never leaves the server. The credential key
    fields are set only by confirming the key a connection test showed."""

    enabled: bool
    service_url: str
    api_key: str | None
    # The public key users' credentials are sealed for, its id and the
    # provider label, as the service reported them when the admin confirmed.
    credential_public_key: str | None
    credential_key_id: str | None
    provider_label: str | None
    # Linked from the users' consent dialog, so company specific wording
    # stays outside the code.
    privacy_policy_url: str | None

    @property
    def is_configured(self) -> bool:
        """Whether Glados can reach the service: a URL and an API key."""
        return bool(self.service_url) and bool(self.api_key)

    @property
    def has_confirmed_key(self) -> bool:
        return bool(self.credential_public_key) and bool(self.credential_key_id)

    @property
    def is_ready(self) -> bool:
        """Switched on, reachable and with a confirmed credential key, so
        users can save credentials and read their data."""
        return self.enabled and self.is_configured and self.has_confirmed_key

    def assert_valid(self) -> None:
        """Raises when time tracking is enabled without a service URL and an
        API key. A missing confirmed key does not block saving, because a
        changed service URL clears it; time tracking stays unavailable to
        users until the admin confirms the key again."""
        if self.enabled and not self.is_configured:
            raise TimeTrackingNotConfiguredError(
                "Enabling time tracking requires the service URL and the API key."
            )
