"""The lifetime cap on new personal access tokens and API keys.

The security setting `token_max_lifetime_days` bounds how long a new token
may live. While it is above 0 every new token needs an expiry, since a token
without one would outlive the cap. A cap of 0 lifts the bound, and a token
may then be created without an expiry. The cap applies to every caller, the
system user included, and only at creation: tokens created before the cap
was lowered keep their expiry.
"""

from datetime import datetime

from src.modules.platform.domain.exceptions import TokenExpiryRequiredError
from src.modules.platform.domain.exceptions import TokenLifetimeExceededError


def token_lifetime_capped(cap_days: int) -> bool:
    """Whether the setting bounds token lifetimes at all."""
    return cap_days > 0


def assert_lifetime_days_allowed(expires_in_days: int | None, cap_days: int) -> None:
    """Raises unless a token lasting `expires_in_days` (None for never) fits
    the cap."""
    if not token_lifetime_capped(cap_days):
        return
    if expires_in_days is None:
        raise TokenExpiryRequiredError(
            f"An expiry is required: tokens may live at most {cap_days} day(s)."
        )
    if expires_in_days > cap_days:
        raise TokenLifetimeExceededError(
            f"expires_in_days ({expires_in_days}) exceeds the configured "
            f"maximum of {cap_days} day(s)."
        )


def assert_expiry_date_allowed(expires_at: datetime | None, now: datetime, cap_days: int) -> None:
    """Raises unless a token expiring at `expires_at` (None for never) fits
    the cap. A token may not live the full cap or longer, since the number
    of whole days between now and the expiry is compared with it."""
    if not token_lifetime_capped(cap_days):
        return
    if expires_at is None:
        raise TokenExpiryRequiredError(
            f"An expiry date is required: tokens may live at most {cap_days} day(s)."
        )
    if (expires_at - now).days >= cap_days:
        raise TokenLifetimeExceededError(
            f"The expiry date exceeds the configured maximum of {cap_days} day(s)."
        )
