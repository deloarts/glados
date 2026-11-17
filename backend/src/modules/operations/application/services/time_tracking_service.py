"""Helpers around the time tracking service: whether time tracking is
usable, the connection a client is built from, and what Glados supports of
the provider contract (docs/reference/time-tracking-provider.md).

Glados states the contract minors it was built against; a connection test
against a service speaking another one warns the admin. Glados renders a
user name and a password field in My Account, so a service asking for any
other required credential field is not supported; optional fields it does
not render are left out of the sealed value.
"""

from src.modules.operations.domain.entities.admin_settings.time_tracking import (
    AdminTimeTrackingSettings,
)
from src.modules.operations.ports.outbound.time_tracking_provider_port import (
    TimeTrackingCredentialField,
)
from src.modules.operations.ports.outbound.time_tracking_provider_port import (
    TimeTrackingServiceConnection,
)

SUPPORTED_CONTRACT_MINORS = frozenset({"0.1"})
SUPPORTED_CREDENTIAL_FIELDS = {"user": "text", "password": "secret"}


def is_time_tracking_available(settings: AdminTimeTrackingSettings) -> bool:
    """Switched on, reachable and with a confirmed credential key."""
    return settings.is_ready


def service_connection(settings: AdminTimeTrackingSettings) -> TimeTrackingServiceConnection:
    """The connection of the saved settings. Callers check is_configured."""
    return TimeTrackingServiceConnection(
        service_url=settings.service_url, api_key=settings.api_key or ""
    )


def contract_supported(contract_version: str) -> bool:
    """Whether the service's contract major.minor is one Glados supports."""
    return ".".join(contract_version.split(".")[:2]) in SUPPORTED_CONTRACT_MINORS


def credential_fields_supported(fields: tuple[TimeTrackingCredentialField, ...]) -> bool:
    """Whether Glados can collect every required field the service asks for,
    and the user and password fields are of the kind Glados renders."""
    by_name = {f.name: f for f in fields}
    for name, kind in SUPPORTED_CREDENTIAL_FIELDS.items():
        field = by_name.get(name)
        if field is not None and field.kind != kind:
            return False
    return all(f.name in SUPPORTED_CREDENTIAL_FIELDS for f in fields if f.required)
