"""
Provider-neutral access to time tracking data. Glados never talks to a time
tracking system itself: a time tracking service in the same stack does, and
this port is the contract Glados defines for it
(docs/reference/time-tracking-provider.md). The application layer calls the
port, never httpx directly; the HTTP implementation lives in
src/modules/operations/adapters/outbound/external/time_tracking_service/.

Credentials only ever pass through here sealed for the service's credential
key, so nothing on this side can read a password. Reads return the value
objects of domain/value_objects/time_tracking.py, with durations in whole
seconds and UTC-aware datetimes. Errors are the domain's TimeTracking*
exceptions (unavailable, authentication failed, permission denied, binding
changed, period invalid, provider error).
"""

from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from typing import Protocol
from typing import runtime_checkable

from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingMonth
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingReadRights


@dataclass(frozen=True)
class TimeTrackingServiceConnection:
    """Where the service runs and the API key Glados calls it with. The key
    is hidden from repr, so a connection never leaks it into a log line."""

    service_url: str
    api_key: str = field(repr=False)


@dataclass(frozen=True)
class TimeTrackingCredentialField:
    """One field the service asks the user for. `kind` is "text" or
    "secret"."""

    name: str
    kind: str
    required: bool
    max_length: int


@dataclass(frozen=True)
class TimeTrackingServiceInfo:
    """What the service reports about itself without touching the system
    behind it: its version, the contract version it implements, the label
    Glados shows, the credential fields, the public key credentials are
    sealed for and its id, and the current binding."""

    service: str
    version: str
    contract_version: str
    provider_label: str
    credential_fields: tuple[TimeTrackingCredentialField, ...]
    credential_public_key: str
    credential_key_id: str
    binding: str


@dataclass(frozen=True)
class TimeTrackingServiceStatus:
    """The connection test's view of the system behind the service."""

    server_version: str
    default_project: str


@dataclass(frozen=True)
class TimeTrackingVerification:
    """A successful credential check. `binding` is stored with the
    credentials; `employee_name` and `rights` are returned, never stored."""

    binding: str
    employee_name: str
    rights: TimeTrackingReadRights


@dataclass(frozen=True)
class TimeTrackingMonthRead:
    employee_name: str
    month: TimeTrackingMonth
    fetched_at: datetime


@dataclass(frozen=True)
class TimeTrackingYearRead:
    """The months of a year up to the current one, in order."""

    employee_name: str
    months: tuple[TimeTrackingMonth, ...]
    fetched_at: datetime


@runtime_checkable
class ITimeTrackingProvider(Protocol):
    async def health(self) -> str:
        """Unauthenticated reachability probe returning the service version."""
        ...

    async def info(self) -> TimeTrackingServiceInfo:
        """Checks the API key and reads the service's self-description."""
        ...

    async def status(self) -> TimeTrackingServiceStatus:
        """Probes the system behind the service without user credentials."""
        ...

    async def verify(self, sealed_credentials: str) -> TimeTrackingVerification:
        """Signs in with the sealed credentials, checks the rights and signs
        out. Raises TimeTrackingAuthenticationFailedError when rejected."""
        ...

    async def month(
        self, sealed_credentials: str, binding: str, year: int, month: int
    ) -> TimeTrackingMonthRead:
        """The user's own month. Raises TimeTrackingPermissionDeniedError
        without the right and TimeTrackingBindingChangedError for a stale
        binding."""
        ...

    async def year(self, sealed_credentials: str, binding: str, year: int) -> TimeTrackingYearRead:
        """The user's own months of `year` up to the current one."""
        ...


# Builds (or returns the shared) provider for a connection, so the admin
# connection test can probe unsaved settings.
type ITimeTrackingProviderFactory = Callable[[TimeTrackingServiceConnection], ITimeTrackingProvider]
