"""
The kinds of security events the security log records, and their outcome.

A login is one type with a success or failure outcome, so the log can be
filtered for every failed login at once. The other types record a change
that happened, so their outcome is success, except a refused password
confirmation, which is a failure.
"""

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


class SecurityEventType(StrValueEnum):
    LOGIN = "login"
    LOGIN_THROTTLED = "login_throttled"
    LOGOUT = "logout"
    PASSWORD_CONFIRMATION = "password_confirmation"
    SESSION_REVOKED = "session_revoked"
    USER_CREATED = "user_created"
    USER_DEACTIVATED = "user_deactivated"
    USER_REACTIVATED = "user_reactivated"
    USER_PERMISSIONS_CHANGED = "user_permissions_changed"
    USER_GROUPS_CHANGED = "user_groups_changed"
    GROUP_CREATED = "group_created"
    GROUP_CHANGED = "group_changed"
    GROUP_DELETED = "group_deleted"
    PAT_CREATED = "pat_created"
    PAT_REVOKED = "pat_revoked"
    API_KEY_CREATED = "api_key_created"
    API_KEY_REVOKED = "api_key_revoked"
    TERMINAL_KEY_CREATED = "terminal_key_created"
    TERMINAL_KEY_REVOKED = "terminal_key_revoked"
    PASSWORD_CHANGED = "password_changed"
    TOTP_ENABLED = "totp_enabled"
    TOTP_DISABLED = "totp_disabled"
    TOTP_RESET = "totp_reset"
    PASSKEY_ADDED = "passkey_added"
    PASSKEY_REMOVED = "passkey_removed"


class SecurityEventOutcome(StrValueEnum):
    SUCCESS = "success"
    FAILURE = "failure"


class LoginMethod(StrValueEnum):
    """How a login proved who the user is, kept in a login event's detail."""

    PASSWORD = "password"
    LDAP = "ldap"
    TOTP = "totp"
    PASSKEY = "passkey"
    TOTP_ENROLMENT = "totp_enrolment"


class LoginRefusal(StrValueEnum):
    """Why a login or a password confirmation was refused, kept in the
    event's detail."""

    INVALID_CREDENTIALS = "invalid_credentials"
    DIRECTORY_UNAVAILABLE = "directory_unavailable"
    INACTIVE = "inactive"
    LOCAL_LOGIN_DISABLED = "local_login_disabled"
    MAINTENANCE = "maintenance"
    INVALID_TOTP = "invalid_totp"
    PASSKEY_REJECTED = "passkey_rejected"
    PASSWORD_REQUIRED = "password_required"
