"""The semantic bases every domain error inherits, and the errors of
Platform itself.

exception_handlers.py maps each semantic base to an HTTP status. An error
needs its own entry there only when its status differs from the one its
base gives it. An error that inherits DomainError directly and has no entry
answers 500 without echoing its message. Every other module keeps its own
errors in its domain/errors.py and inherits the bases from here."""


class DomainError(Exception):
    """Base for all domain errors."""


# ── Semantic bases ────────────────────────────────────────────────────


class BadRequestError(DomainError):
    """The request cannot be carried out as asked, usually because an
    integration is not configured, a setting is invalid or an external
    system rejected the credentials it was given."""


class AuthenticationError(DomainError):
    """The caller could not be authenticated, for example because a
    token, code or challenge is wrong or expired."""


class ForbiddenError(DomainError):
    """The caller is known but is not allowed to do this."""


class NotFoundError(DomainError):
    """The requested record or resource does not exist."""


class ConflictError(DomainError):
    """The request clashes with the current state of the data, for
    example a duplicate, a released or locked record, a status that no
    longer allows the change, or a concurrent change."""


class PayloadTooLargeError(DomainError):
    """An uploaded file exceeds its size limit."""


class UnsupportedFileTypeError(DomainError):
    """An uploaded file has a type that is not accepted."""


class InvalidInputError(DomainError):
    """The input is well formed but breaks a domain rule, for example
    a quantity, status transition, pattern or selection the rules do not
    allow."""


class RateLimitedError(DomainError):
    """The caller sent too many requests and has to wait before
    trying again."""


class ExternalServiceError(DomainError):
    """An external system answered, but with an error or a response
    Glados cannot use."""


class ServiceUnavailableError(DomainError):
    """A feature or external system the request needs is unavailable
    right now."""


class ServiceUnreachableError(ServiceUnavailableError):
    """An external system the request needs could not be reached at all,
    for example because of DNS, TCP, TLS or a timeout. The handler logs it
    as an error, since an operator has to look at the connection."""


# ── Quantities ────────────────────────────────────────────────────────


class FractionalPiecesError(InvalidInputError):
    """A quantity counted in pieces, sets, pairs or other whole units is not
    a whole number: lots, production orders, completions and scrap always
    count pieces, a demand or order line does when its unit does."""


# ── Users, passwords and two-factor authentication ────────────────────


class UserNotFoundError(NotFoundError):
    pass


class UsernameAlreadyExistsError(ConflictError):
    pass


class EmailAlreadyExistsError(ConflictError):
    pass


class ReservedUsernameError(ConflictError):
    """The username is reserved for the break-glass system account.

    `system` is exempt from directory authentication by name (see
    login_policy.resolves_to_ldap), so letting another account claim it would
    be a permanent LDAP bypass."""


class RfidAlreadyExistsError(ConflictError):
    pass


class PasswordCriteriaError(InvalidInputError):
    pass


class PasswordNotAllowedError(BadRequestError):
    """A local password was supplied for a directory-authenticated account,
    which has no local fallback; the next bind would discard it."""


class InsufficientPermissionsError(ForbiddenError):
    pass


class SystemUserProtectedError(InsufficientPermissionsError):
    pass


class InactiveUserError(ForbiddenError):
    pass


class InvalidSharedAccountMemberError(InvalidInputError):
    pass


# ── User groups ───────────────────────────────────────────────────────


class UserGroupNotFoundError(NotFoundError):
    pass


class UserGroupNameTakenError(ConflictError):
    """Another group already has this name, compared regardless of case."""


class InvalidUserGroupError(InvalidInputError):
    """A group's name, permissions or members are not acceptable, or a user
    was put into a group that does not exist or cannot hold members of
    that kind."""


class OwnUserGroupError(InsufficientPermissionsError):
    """The actor tried to change their own group memberships or the
    permissions of a group they belong to, which would let them grant
    themselves permissions."""


class InvalidTokenError(AuthenticationError):
    pass


class InvalidTOTPCodeError(AuthenticationError):
    pass


class TOTPNotEnabledError(BadRequestError):
    pass


class TOTPAlreadyEnabledError(ConflictError):
    """2FA is on, so a new secret would replace the active one without proof
    of the current factor. The user turns 2FA off first, which asks for a
    current code, and then enrols again."""


class TOTPChallengeInvalidError(AuthenticationError):
    """The 2FA challenge token is unusable for any reason, so the client
    must start over from the credentials form. InvalidTOTPCodeError instead
    means the challenge is still live and only needs a retry."""

    pass


# ── Login methods and directory authentication ────────────────────────


class LocalLoginDisabledError(ForbiddenError):
    """Password login is switched off in admin settings."""


class RfidDisabledError(ForbiddenError):
    """RFID operator identification is switched off in admin settings."""


class LdapUnavailableError(ServiceUnreachableError):
    """The directory could not be reached, DNS, TCP, TLS, timeout, or a
    misconfiguration. The credentials were never judged.

    Callers may treat this as "unknown" and fall back to a locally cached
    password; they must never do so for LdapAuthenticationFailedError."""


class LdapAuthenticationFailedError(BadRequestError):
    """The directory was reached and rejected the credentials.

    Never raised on the login path, AuthenticateUser converts it to the
    generic UserNotFoundError so the public endpoint stays a uniform 401."""


class LdapNotConfiguredError(BadRequestError):
    pass


class CredentialsUnverifiableError(UserNotFoundError):
    """The credential could not be judged because the directory is
    unreachable. It answers with the same 401 as a wrong password but must
    not count toward lockout, since nothing was guessed."""


class LoginLockedError(RateLimitedError):
    """Too many failed password or TOTP attempts locked this login for a
    while. `retry_after_seconds` is how long the lock still holds; the login
    routes answer with it as the Retry-After header."""

    def __init__(self, message: str, *, retry_after_seconds: int) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


# ── Sessions and trusted devices ──────────────────────────────────────


class SessionNotFoundError(NotFoundError):
    pass


class TrustedDeviceNotFoundError(NotFoundError):
    pass


# ── Passkeys ──────────────────────────────────────────────────────────


class PasskeyNotFoundError(NotFoundError):
    pass


class PasswordConfirmationFailedError(BadRequestError):
    """The password typed to confirm a sensitive change on the caller's own
    account was wrong. A 400 rather than a 401, because the session itself is
    still valid and a 401 would sign the caller out."""


class CurrentPasswordRequiredError(InvalidInputError):
    """A user making a change on their own account that needs the current
    password, such as setting a new password or setting up 2FA, did not give
    it. An administrator setting someone else's password is not asked for
    it."""


class PasskeyRegistrationFailedError(BadRequestError):
    """The browser's registration response did not verify, or its challenge
    expired or was already used. A 400 for the same reason as
    PasswordConfirmationFailedError."""


class PasskeyRejectedError(AuthenticationError):
    """A passkey login failed: the challenge is expired or used, the
    credential is unknown, or the signature did not verify. One error for
    all of them, so the public login route reveals nothing about which."""


class PasskeyPasswordRequiredError(ForbiddenError):
    """The passkey verified, but its owner is a directory account whose
    password was not checked against the directory recently enough. A
    passkey login never reaches the directory, so a password login now and
    then is what stops a disabled directory account from living on here."""


# ── API keys and personal access tokens ───────────────────────────────


class ApiKeyNotFoundError(NotFoundError):
    pass


class ExcessiveApiKeyPermissionsError(ForbiddenError):
    """Raised when a requested permission set includes settings permissions,
    unknown permissions, or permissions the creator does not themselves hold."""


class PatNotFoundError(NotFoundError):
    pass


class ExcessivePatPermissionsError(ForbiddenError):
    """Raised when a requested permission set includes settings permissions,
    unknown permissions, or permissions the creator does not themselves hold."""


class TokenLifetimeExceededError(InvalidInputError):
    """A token lifetime exceeds the configured maximum, which applies to
    every caller including the system user."""


class TokenExpiryRequiredError(InvalidInputError):
    """A new token was asked for without an expiry while the security
    settings cap token lifetimes, so it would outlive the cap."""


# ── Tenant holidays and calendars ─────────────────────────────────────


class TenantHolidayNotFoundError(NotFoundError):
    pass


class InvalidScheduleCalendarError(InvalidInputError):
    pass


# ── File storage ──────────────────────────────────────────────────────


class StorageMigrationError(BadRequestError):
    pass


class StorageProviderInvalidError(BadRequestError):
    """The requested storage provider is not one Glados supports."""


class StorageMigrationInProgressError(ConflictError):
    """Another storage migration holds the app-wide mutex. Two at once would
    both copy every file and race to switch the settings."""


class StorageNotEnabledError(ServiceUnavailableError):
    pass


class StorageConnectionError(BadRequestError):
    pass


class StoragePathError(BadRequestError):
    """A storage key resolves outside the storage root.

    Only the local filesystem provider can be affected, S3/Azure treat
    keys as opaque strings, so `..` is just part of the name there.
    """


class StoragePublicUrlUnavailableError(DomainError):
    """The storage adapter cannot produce a public URL for a key. Local
    storage always raises this; callers treat get_url as optional and never
    as a liveness signal."""


# ── Avatars and login branding ────────────────────────────────────────


class AvatarTooLargeError(PayloadTooLargeError):
    pass


class AvatarInvalidTypeError(UnsupportedFileTypeError):
    pass


class AvatarNotFoundError(NotFoundError):
    pass


class LoginVideoTooLargeError(PayloadTooLargeError):
    pass


class LoginVideoInvalidTypeError(UnsupportedFileTypeError):
    pass


class LoginVideoNotFoundError(NotFoundError):
    pass


class BrandingImageTooLargeError(PayloadTooLargeError):
    pass


class BrandingImageInvalidTypeError(UnsupportedFileTypeError):
    pass


class BrandingImageNotFoundError(NotFoundError):
    pass


# ── Notifications and announcements ───────────────────────────────────


class NotificationNotFoundError(NotFoundError):
    pass


class AcknowledgementNotFoundError(NotFoundError):
    """Also raised by AcknowledgeAnnouncement when the caller is not a
    recipient of the acknowledgement, or it is disabled. The same 404 as
    "does not exist" on purpose, so the endpoint never confirms to a
    non-recipient which acknowledgements exist."""


class AcknowledgementRecipientsInvalidError(InvalidInputError):
    """Raised by CreateAcknowledgement for an empty recipient list or a
    recipient id that names no existing user."""


# ── Mail ──────────────────────────────────────────────────────────────


class MailNotEnabledError(BadRequestError):
    pass


class MailNotConfiguredError(BadRequestError):
    pass


class SmtpDeliveryError(ExternalServiceError):
    pass


class MailRateLimitedError(RateLimitedError):
    pass


class MailAttachmentsTooLargeError(PayloadTooLargeError):
    """The attachments of a composed mail add up to more than the admin
    limit allows. The message names the files that do not fit."""


class MailTemplateRenderError(BadRequestError):
    """A mail template has bad Jinja syntax or uses an undefined variable.
    The Jinja message is returned so the editor can show it inline."""


# ── Time tracking ─────────────────────────────────────────────────────


class TimeTrackingCredentialsNotAllowedError(ConflictError):
    """Shared, service and system accounts cannot hold time tracking
    credentials, only personal accounts can."""


# ── Webhooks ──────────────────────────────────────────────────────────


class WebhookSubscriptionNotFoundError(NotFoundError):
    pass


class WebhookDeliveryNotFoundError(NotFoundError):
    pass


class InvalidWebhookConfigurationError(BadRequestError):
    pass


class WebhookDeliveryFailedError(DomainError):
    """At least one subscriber did not accept the event. The event bus worker
    catches this to keep the message pending for redelivery."""


# ── Backups ───────────────────────────────────────────────────────────


class BackupError(DomainError):
    pass


class BackupNotConfiguredError(BackupError):
    pass


class BackupAlreadyRunningError(BackupError):
    """A backup is already running. This is a UX gate only; the advisory
    lock taken before the jobs run protects the data."""


# ── Terminal permission ───────────────────────────────────────────────


class TerminalPermissionNotAssignableError(InvalidInputError):
    """The terminal connect permission belongs to terminal keys alone and
    cannot be given to or taken from a user by hand."""


# ── Maintenance mode ──────────────────────────────────────────────────


class MaintenanceModeError(ServiceUnavailableError):
    """Raised for a non-exempt caller while maintenance mode is on. The
    message is admin-editable; the frontend keys on the code only."""


# ── Localized text and public ids ─────────────────────────────────────


class LocalizedTextInvalidError(InvalidInputError):
    """A localized label names an unknown language or lacks the text in the
    instance's default language."""


class PublicIdNotFoundError(NotFoundError):
    pass


# ── Concurrency ───────────────────────────────────────────────────────


class ConcurrentModificationError(ConflictError):
    """Another request changed what this one read before it could lock or
    write it. Nothing was written; repeating the request works on the
    current state."""


class NumberingConflictError(ConflictError):
    """A concurrent creation took the derived lot or production order
    number first. Benign and retryable (see retry_on_conflict.py)."""

    pass


# ── Idempotency keys ──────────────────────────────────────────────────


class IdempotencyKeyInvalidError(InvalidInputError):
    """An Idempotency-Key header that is empty, too long or not printable."""


class IdempotencyKeyReusedError(InvalidInputError):
    """An Idempotency-Key the user already sent with a different request.
    A key stands for one user action, so a retry repeats the request
    exactly."""


class IdempotencyKeyInFlightError(ConflictError):
    """The first request with this Idempotency-Key has not finished yet, so
    its outcome cannot be replayed. Trying again shortly answers with it."""


# ── AI agents (MCP) ───────────────────────────────────────────────────


class AgentAccessDisabledError(ForbiddenError):
    """The MCP surface is switched off in the agent settings."""


class AgentAccessNotApprovedError(InvalidInputError):
    """The agent settings switch agent access on without the company's
    approval of AI processing, or record an approval that names no
    provider."""


class AgentConsentRequiredError(ForbiddenError):
    """The token's owner has not confirmed the current agent consent, or
    confirmed it before the terms last changed."""


class AgentConsentOutdatedError(InvalidInputError):
    """A user confirmed a consent text other than the current one."""


class AgentOriginRefusedError(ForbiddenError):
    """A browser origin outside the agent settings' allowlist called the
    MCP surface."""


class AgentTokenNotAllowedError(ForbiddenError):
    """The token is valid but may not be used by an agent: it lacks
    use:mcp, or it is a terminal key."""


class AgentBudgetExceededError(RateLimitedError):
    """An agent token spent its call or draft budget for now."""


class AgentToolNotAllowedError(ForbiddenError):
    """The tool is not open to this token, such as a draft tool for an API
    key, which acts without a person behind it."""
