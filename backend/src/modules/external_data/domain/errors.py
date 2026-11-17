"""The domain errors of CAD & external data.

Each error inherits a semantic base from Platform's domain/exceptions.py,
which the exception handler maps to an HTTP status. The response carries
the class name as its `code`, which clients and translations match on, so
an error keeps its name once it has shipped."""

from src.modules.platform.domain.exceptions import BadRequestError
from src.modules.platform.domain.exceptions import ConflictError
from src.modules.platform.domain.exceptions import ExternalServiceError
from src.modules.platform.domain.exceptions import ForbiddenError
from src.modules.platform.domain.exceptions import NotFoundError
from src.modules.platform.domain.exceptions import RateLimitedError
from src.modules.platform.domain.exceptions import ServiceUnreachableError

# ── Admin settings ────────────────────────────────────────────────────


class AdminSettingsNotFoundError(NotFoundError):
    pass


# ── SolidWorks PDM ────────────────────────────────────────────────────


class PdmNotConfiguredError(BadRequestError):
    """The connection fields (base_url, vault_name, username, password) are
    not all set; raised before any call to the vault is attempted."""


class PdmAuthenticationFailedError(BadRequestError):
    """The vault was reached and rejected the credentials."""


class PdmUnavailableError(ServiceUnreachableError):
    """The vault's Web API could not be reached at all, DNS, TCP, TLS or
    timeout. The credentials were never judged."""


class PdmApiError(ExternalServiceError):
    """The vault answered with a non-2xx status other than 401. Carries the
    PDM status code and response body text so the admin API console can
    show them; the message never includes the bearer token."""

    def __init__(self, message: str, *, status_code: int, body: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class PdmSessionExpiredError(ExternalServiceError):
    """Internal 401 signal from the gateway to PdmSessionService: the
    stored bearer token is no longer valid and a re-authenticate is
    needed. Never escalates past the session service."""


class PdmOperationNotAllowedError(BadRequestError):
    """The admin API console invoked a catalogued mutating operation
    without `allow_mutating: true`: a live-vault, irreversible call that
    requires the caller to opt in per visit."""


class PdmMutatingOperationsDisabledError(ForbiddenError):
    """The admin API console invoked a mutating operation while the
    deployment leaves them off (PDM__ALLOW_MUTATING_OPERATIONS)."""


class PdmUnknownOperationError(NotFoundError):
    """The admin API console invoked an operation id absent from the
    catalogue."""


class PdmOperationParametersInvalidError(BadRequestError):
    """The admin API console call has unusable path parameters: a required
    one is missing, the caller supplied `vaultName` (always filled in from
    the saved connection), or the generic `uri` contains `..` segments."""


class PdmVaultMismatchError(BadRequestError):
    """A file-changed trigger named a vault other than the configured
    one."""


class PdmSettingsInvalidError(BadRequestError):
    """PDM settings violate a cross-field rule that needs the stored
    settings to evaluate, such as enabling without a connection, folder or
    released state."""


class PdmNotEnabledError(ConflictError):
    """A manual poll or a file-changed trigger was requested while the PDM
    integration is not enabled and configured (is_pdm_enabled() is
    False)."""


class PdmTriggerRateLimitedError(RateLimitedError):
    """One actor (the owner of a PAT, such as a vault user, or an API key's
    service account) sent more than the in-process trigger limit's
    allowance of PDM file-changed requests within its window. See
    PdmTriggerRateLimiter."""


class PdmFileNotFoundError(NotFoundError):
    """The vault does not report the file, or the session cannot read it.
    Both mean nothing to validate and share one 404."""


# ── Stock service ─────────────────────────────────────────────────────


class StockServiceNotConfiguredError(BadRequestError):
    """The stock service settings lack the service URL or the API key, so
    the stock service cannot be enabled or the connection cannot be
    tested."""


class StockServiceProviderError(ExternalServiceError):
    """The stock service or the system behind it answered with an error, an
    unexpected status, a redirect or an unparsable body, or the service
    refused Glados' API key."""


class StockServiceUnavailableError(ServiceUnreachableError):
    """The stock service, or the system behind it, could not be reached at
    all (DNS, TCP, TLS or timeout)."""


# ── EPLAN Data Portal ─────────────────────────────────────────────────


class EdpNotConfiguredError(BadRequestError):
    """The EPLAN Data Portal is switched off or has no personal access
    token, so a lookup cannot run."""


class EdpAuthenticationFailedError(BadRequestError):
    """The Data Portal refused the personal access token: expired, revoked
    or not issued for the Data Portal."""


class EdpUnavailableError(ServiceUnreachableError):
    """The Data Portal could not be reached or timed out."""


class EdpPartNotFoundError(NotFoundError):
    """The EPLAN Data Portal does not know the part id it was asked for."""


class EdpProviderError(ExternalServiceError):
    """The Data Portal answered with something Glados could not use."""


class EdpSettingsInvalidError(BadRequestError):
    """The Data Portal settings break a rule: an invalid base URL, enabling
    without a token, or an unsupported designation language."""
