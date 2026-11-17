"""
HTTP request and response schemas for the authentication provider (LDAP)
settings and the LDAP connection check.
"""

from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse


class UpdateAuthSettingsRequest(BaseModel):
    ldap_enabled: bool = False
    ldap_host: str = ""
    ldap_port: int = Field(default=636, ge=1, le=65535)
    ldap_use_ssl: bool = True
    ldap_start_tls: bool = False
    ldap_verify_certificate: bool = True
    ldap_domain: str = ""
    ldap_timeout_seconds: int = Field(default=5, ge=1, le=120)


class VerifyLdapConnectionRequest(UpdateAuthSettingsRequest):
    username: str
    password: str


class AdminAuthSettingsResponse(EntityResponse):
    ldap_enabled: bool
    ldap_host: str
    ldap_port: int
    ldap_use_ssl: bool
    ldap_start_tls: bool
    ldap_verify_certificate: bool
    ldap_domain: str
    ldap_timeout_seconds: int
