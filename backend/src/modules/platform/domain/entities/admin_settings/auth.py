"""
Domain entity for the authentication provider (LDAP) settings singleton.
"""

from dataclasses import dataclass

from src.shared_kernel.domain.entities.base import Entity


@dataclass
class AdminAuthSettings(Entity):
    """Authentication providers.

    LDAP authentication is a direct simple bind as the end user
    (f"{ldap_domain}\\{user.username}"), there is no service account and no
    directory search, because users are never auto-created and no directory
    attribute is ever read. That is deliberate: nothing here is a secret, so
    this entity has no "keep existing" field and no *_configured flag.
    """

    ldap_enabled: bool
    ldap_host: str  # DC hostname, e.g. "dc-01.corp.example"
    ldap_port: int  # 636 for LDAPS, 389 for plain/StartTLS
    ldap_use_ssl: bool  # implicit TLS (LDAPS), mutually exclusive with start_tls
    ldap_start_tls: bool  # StartTLS on a plain 389 connection
    # True (ssl.CERT_REQUIRED) for new installs; False is the opt-out for an
    # internal CA the system trust store does not know.
    ldap_verify_certificate: bool
    ldap_domain: str  # NetBIOS domain used for the bind, e.g. "CORP"
    # TCP connect + response timeout. Load-bearing: without it an unreachable
    # DC blocks on connect for ~2 minutes, holding a worker thread per login.
    ldap_timeout_seconds: int
