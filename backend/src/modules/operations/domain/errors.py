"""The domain errors of Operations.

Each error inherits a semantic base from Platform's domain/exceptions.py,
which the exception handler maps to an HTTP status. The response carries
the class name as its `code`, which clients and translations match on, so
an error keeps its name once it has shipped."""

from src.modules.platform.domain.exceptions import AuthenticationError
from src.modules.platform.domain.exceptions import BadRequestError
from src.modules.platform.domain.exceptions import ConflictError
from src.modules.platform.domain.exceptions import ExternalServiceError
from src.modules.platform.domain.exceptions import ForbiddenError
from src.modules.platform.domain.exceptions import InvalidInputError
from src.modules.platform.domain.exceptions import NotFoundError
from src.modules.platform.domain.exceptions import RateLimitedError
from src.modules.platform.domain.exceptions import ServiceUnavailableError
from src.modules.platform.domain.exceptions import ServiceUnreachableError

# ── Terminals and infoscreens ─────────────────────────────────────────


class TerminalNotFoundError(NotFoundError):
    pass


class InfoscreenNotFoundError(NotFoundError):
    pass


class InfoscreenNameTakenError(ConflictError):
    """Another live screen already has this name."""


class InvalidInfoscreenConfigError(InvalidInputError):
    """A screen's settings, pages or widget configs break a rule, such as a
    slot count that does not match the page layout."""


class InfoscreenArchivedError(InvalidInputError):
    """An archived screen cannot be assigned to a terminal."""


class TerminalModeNotSupportedError(InvalidInputError):
    """The terminal mode is reserved and cannot be chosen yet."""


class TerminalNotPendingError(ConflictError):
    """Only a pending terminal can be approved."""


class PairingCodeMismatchError(InvalidInputError):
    """The typed pairing code is not the one the terminal shows."""


class PairingCodeExpiredError(InvalidInputError):
    """The terminal's pairing code expired; the device shows a new one
    after its next session."""


class PendingTerminalLimitError(ConflictError):
    """Too many terminals are waiting for approval to register another."""


class TerminalNotReadyError(ConflictError):
    """The terminal is not approved or has no screen assigned, so it has no
    feed to show."""


class TerminalsDisabledError(ForbiddenError):
    """Terminal sign-in is switched off in the security settings."""


class TerminalIpNotAllowedError(ForbiddenError):
    """The client address is not on the terminal allowlist."""


class TerminalChallengeError(AuthenticationError):
    """The challenge nonce is malformed, expired, bound to another key or
    already used."""


class TerminalSignatureError(AuthenticationError):
    """The device's signature over the challenge does not verify."""


class TerminalKeyRequiredError(AuthenticationError):
    """An unknown device sent no terminal key, which its first session
    needs."""


class InvalidTerminalKeyError(AuthenticationError):
    """The terminal key sent by an unknown device is unknown, revoked or
    expired."""


class NotATerminalKeyError(ForbiddenError):
    """The API key sent by an unknown device is not a terminal key."""


class TerminalTokenInvalidError(AuthenticationError):
    """The terminal access token is missing, malformed, expired or names a
    terminal that no longer exists."""


class TerminalAuthRateLimitedError(RateLimitedError):
    """One client address sent more terminal challenge or session requests
    than the in-process limit allows within its window."""


class InfoscreenThumbnailNotFoundError(NotFoundError):
    """The thumbnail link is expired or forged, or its item is archived or
    has no picture."""


class InfoscreenDrawingNotFoundError(NotFoundError):
    """The drawing link is expired or forged, or its item is archived or no
    longer has that drawing."""


class WeatherUnavailableError(ServiceUnavailableError):
    """The weather service could not answer and no earlier forecast stands
    in, or an admin switched the weather off."""


class InvalidDisplayOverrideError(InvalidInputError):
    """A display override names an unknown power, ends in the past, lasts
    too long, or has no end while the screen's schedule foresees no change."""


class InvalidTerminalLocationError(InvalidInputError):
    """A terminal's location text is too long."""


class TerminalBroadcastNotFoundError(NotFoundError):
    pass


class InvalidTerminalBroadcastError(InvalidInputError):
    """A message to terminals breaks a rule: an empty or too long text, an
    end in the past or too far ahead, an empty pick, or a target that does
    not exist."""


class TokenExpiryInPastError(InvalidInputError):
    """A new token's expiry date lies in the past."""


# ── Time tracking ─────────────────────────────────────────────────────


class TimeTrackingNotEnabledError(ConflictError):
    """Time tracking is switched off, or the time tracking service is not
    fully set up (URL, API key and a confirmed credential key)."""


class TimeTrackingCredentialsMissingError(BadRequestError):
    """The user has no usable stored credentials: none were saved, they can
    no longer be decrypted, or they were sealed for another service, server
    or key. The user enters them again in My Account."""


class TimeTrackingAuthenticationFailedError(BadRequestError):
    """The time tracking system rejected the credentials, or an earlier
    rejection of the stored credentials blocks further calls until the user
    saves them again. Mapped to 400, not 401, so the client never mistakes
    it for an expired Glados session."""


class TimeTrackingPermissionDeniedError(ForbiddenError):
    """The time tracking system refused a read the user's own account has no
    right for."""


class TimeTrackingProviderError(ExternalServiceError):
    """The time tracking service or the system behind it answered with an
    error, an unexpected status, a redirect or an unparsable body, or the
    service refused Glados' API key. Never carries credentials."""


class TimeTrackingUnavailableError(ServiceUnreachableError):
    """The time tracking service, or the system behind it, could not be
    reached at all (DNS, TCP, TLS or timeout)."""


class TimeTrackingBindingChangedError(BadRequestError):
    """The stored credentials were sealed and verified for another server or
    credential key than the time tracking service uses now. Glados cannot
    re-seal them, so the user enters the password again."""


class TimeTrackingKeyChangedError(ConflictError):
    """The credential key to confirm is not the one the time tracking
    service serves now. The admin tests the connection again."""


class TimeTrackingRateLimitedError(RateLimitedError):
    """Too many failed credential checks, or a journal fetch repeated within
    the per-user cooldown."""


class TimeTrackingUserAlreadyLinkedError(ConflictError):
    """The time tracking user name is already stored for another Glados
    user. The message never says which one."""


class TimeTrackingConsentRequiredError(BadRequestError):
    """Saving credentials needs a confirmation of the current consent text,
    or the stored confirmation belongs to an older text."""


class TimeTrackingPeriodInvalidError(BadRequestError):
    """A requested month or year lies in the future."""


class TimeTrackingNotConfiguredError(BadRequestError):
    """The time tracking settings lack the service URL or the API key, or no
    credential key is confirmed yet, so time tracking cannot be enabled or
    the connection cannot be tested."""
