"""Provider-neutral rules for per-user time tracking credentials: the input
limits for values that travel to the time tracking system, the consent text
version, when stored credentials are usable, and the limits that keep
Glados from hammering or locking accounts on the time tracking system.

User name and password typically end up in an HTTP auth header on the far
side, so a colon in the user name or a control character anywhere would
corrupt it. Stored credentials are sealed for one credential key of the time
tracking service and verified against the server behind it; the stored
binding and key id record which, and credentials sealed for another key, or
cleared after the service reported a changed binding, are not usable.

Failed credential checks are counted per Glados user and lock further
checks for a while, which stops the save form from being used to guess a
colleague's password or to lock their account. Successful checks never
reset that count, otherwise interleaving one's own valid credentials would
lift the limit. Fetches are spaced per user and kind.
"""

import re
from enum import StrEnum

from src.modules.operations.domain.entities.user_time_tracking_credentials import (
    UserTimeTrackingCredentials,
)
from src.modules.operations.domain.errors import TimeTrackingAuthenticationFailedError
from src.modules.operations.domain.errors import TimeTrackingConsentRequiredError
from src.modules.operations.domain.errors import TimeTrackingCredentialsMissingError

# Raised whenever the consent dialog text changes in a way users must
# confirm again; stored consent of an older version blocks every call.
TIME_TRACKING_CONSENT_VERSION = 2

VERIFY_FAILURE_LIMIT = 5
VERIFY_LOCK_SECONDS = 15 * 60
FETCH_COOLDOWN_SECONDS = 5

USER_MAX_LENGTH = 128
PASSWORD_MAX_LENGTH = 256

_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")


class CredentialsInvalidReason(StrEnum):
    """Why stored credentials cannot be used, from Glados state alone."""

    MISSING = "missing"
    UNDECRYPTABLE = "undecryptable"
    BINDING_CHANGED = "binding_changed"
    AUTH_FAILED = "auth_failed"
    CONSENT_OUTDATED = "consent_outdated"


def validate_time_tracking_user(value: str) -> str:
    """The trimmed user name. Raises ValueError when it is empty, too long,
    or contains a colon or a control character."""
    trimmed = value.strip()
    if not trimmed:
        raise ValueError("time_tracking_user must not be empty.")
    if len(trimmed) > USER_MAX_LENGTH:
        raise ValueError(f"time_tracking_user must be at most {USER_MAX_LENGTH} characters.")
    if ":" in trimmed or _CONTROL_CHARACTERS.search(trimmed):
        raise ValueError("time_tracking_user must not contain ':' or control characters.")
    return trimmed


def validate_time_tracking_password(value: str) -> str:
    """The password as entered. Raises ValueError when it is empty, too
    long or contains a control character. The message never repeats it."""
    if not value:
        raise ValueError("time_tracking_password must not be empty.")
    if len(value) > PASSWORD_MAX_LENGTH:
        raise ValueError(
            f"time_tracking_password must be at most {PASSWORD_MAX_LENGTH} characters."
        )
    if _CONTROL_CHARACTERS.search(value):
        raise ValueError("time_tracking_password must not contain control characters.")
    return value


def fingerprint_subject(time_tracking_user: str) -> str:
    """What the one-account-per-user fingerprint is computed over: the
    trimmed, casefolded user name, so the same account typed with different
    case or spacing still collides."""
    return time_tracking_user.strip().casefold()


def credentials_invalid_reason(
    credentials: UserTimeTrackingCredentials | None, *, current_key_id: str | None
) -> CredentialsInvalidReason | None:
    """None when the stored credentials may be used for a call, else the
    first reason they may not, in the order a user would fix them.
    `current_key_id` is the id of the confirmed credential key."""
    if credentials is None:
        return CredentialsInvalidReason.MISSING
    if not credentials.time_tracking_user:
        return CredentialsInvalidReason.UNDECRYPTABLE
    if (
        not credentials.time_tracking_sealed_credentials
        or credentials.time_tracking_credential_key_id != current_key_id
    ):
        return CredentialsInvalidReason.BINDING_CHANGED
    if credentials.time_tracking_auth_failed_at is not None:
        return CredentialsInvalidReason.AUTH_FAILED
    if credentials.time_tracking_consent_version != TIME_TRACKING_CONSENT_VERSION:
        return CredentialsInvalidReason.CONSENT_OUTDATED
    return None


def assert_credentials_usable(
    credentials: UserTimeTrackingCredentials | None, *, current_key_id: str | None
) -> UserTimeTrackingCredentials:
    """Returns the credentials when they may be used, else raises the error
    matching the reason. No request reaches the time tracking service for
    unusable credentials."""
    reason = credentials_invalid_reason(credentials, current_key_id=current_key_id)
    if reason is CredentialsInvalidReason.MISSING:
        raise TimeTrackingCredentialsMissingError(
            "No time tracking credentials are stored. Enter them in My Account."
        )
    if reason is CredentialsInvalidReason.UNDECRYPTABLE:
        raise TimeTrackingCredentialsMissingError(
            "The stored time tracking credentials can no longer be read. Please enter them again."
        )
    if reason is CredentialsInvalidReason.BINDING_CHANGED:
        raise TimeTrackingCredentialsMissingError(
            "The time tracking server or key has changed, please enter your password again."
        )
    if reason is CredentialsInvalidReason.AUTH_FAILED:
        raise TimeTrackingAuthenticationFailedError(
            "The time tracking system rejected the stored credentials. Please enter them again."
        )
    if reason is CredentialsInvalidReason.CONSENT_OUTDATED:
        raise TimeTrackingConsentRequiredError(
            "The consent text has changed. Please confirm it again in My Account."
        )
    assert credentials is not None  # None maps to MISSING above
    return credentials


def assert_consent_current(version: int | None) -> None:
    """Saving credentials requires confirming the current consent text."""
    if version != TIME_TRACKING_CONSENT_VERSION:
        raise TimeTrackingConsentRequiredError(
            "Saving time tracking credentials requires confirming the current consent text."
        )


def verify_limit_exceeded(failures: int) -> bool:
    """True once the failed checks, including this one, reach the limit."""
    return failures >= VERIFY_FAILURE_LIMIT
