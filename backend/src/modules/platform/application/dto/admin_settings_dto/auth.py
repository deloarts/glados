"""
Commands and results for the authentication provider (LDAP) settings and the
LDAP connection check.
"""

from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.application.dto.base import ResultBase


class UpdateAuthSettingsCommand(BaseModel):
    """LDAP binds directly as the end user, so this domain stores no secret,
    there is deliberately no "None means keep existing" field here."""

    ldap_enabled: bool = False
    ldap_host: str = ""
    ldap_port: int = Field(default=636, ge=1, le=65535)
    ldap_use_ssl: bool = True
    ldap_start_tls: bool = False
    ldap_verify_certificate: bool = True
    ldap_domain: str = ""
    # Bounded rather than merely positive: an unreachable DC holds a worker
    # thread for this long on every login attempt.
    ldap_timeout_seconds: int = Field(default=5, ge=1, le=120)


class VerifyLdapConnectionCommand(UpdateAuthSettingsCommand):
    """The settings to probe, plus a directory account to bind with.

    Neither credential is stored or logged, this is a transient connectivity
    probe. A username and password are required because binding is done as the
    end user; there is no service account to fall back on.
    """

    username: str
    password: str


class AdminAuthSettingsResult(ResultBase):
    ldap_enabled: bool
    ldap_host: str
    ldap_port: int
    ldap_use_ssl: bool
    ldap_start_tls: bool
    ldap_verify_certificate: bool
    ldap_domain: str
    ldap_timeout_seconds: int
