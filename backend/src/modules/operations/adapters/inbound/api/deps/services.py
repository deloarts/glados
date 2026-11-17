"""Adapter and service factories, and the services one process shares
between requests."""

from src.modules.operations.adapters.outbound.external.time_tracking_service.factory import (
    create_time_tracking_provider,
)
from src.modules.operations.application.services.terminal_auth_rate_limiter import (
    TerminalAuthRateLimiter,
)
from src.modules.operations.ports.outbound.time_tracking_provider_port import (
    ITimeTrackingProviderFactory,
)


def get_time_tracking_provider_factory() -> ITimeTrackingProviderFactory:
    """The time tracking service client factory, for the time tracking use
    cases and the admin connection test, which may probe unsaved settings."""
    return create_time_tracking_provider


# One per process, because its window spans requests.
_terminal_auth_rate_limiter = TerminalAuthRateLimiter()


def get_terminal_auth_rate_limiter() -> TerminalAuthRateLimiter:
    return _terminal_auth_rate_limiter
