"""
Input commands and output results for user use cases.
These cross the application boundary, what the inbound adapter sends in,
what it gets back. Not the same as API schemas (those live in the adapter layer).
"""

from datetime import datetime

from pydantic import BaseModel
from pydantic import EmailStr

from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.domain.value_objects.auth_provider import AuthProvider
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.start_page import StartPage
from src.modules.platform.domain.value_objects.theme import ThemePreset
from src.modules.platform.domain.value_objects.theme import ThemePrimary
from src.modules.platform.domain.value_objects.theme import ThemeSurface

# ── Commands (inbound) ────────────────────────────────────────────────


class CreateUserCommand(BaseModel):
    username: str
    full_name: str
    email: EmailStr
    # None for a directory-backed account, which has no local password at all.
    # The HTTP schema enforces that pairing; see UserCreateRequest.
    password: str | None = None
    rfid: str | None = None

    is_active: bool = True
    is_shared_account: bool = False
    auth_provider: str = AuthProvider.LOCAL
    member_ids: list[int] = []
    group_ids: list[int] = []
    permissions: list[str] = []

    language: Language | None = None
    date_format: DateFormat | None = None
    start_page: StartPage | None = None
    theme_preset: ThemePreset | None = None
    theme_surface: ThemeSurface | None = None
    theme_primary: ThemePrimary | None = None
    theme_dark_mode: bool | None = None
    button_flat_style: bool | None = None
    table_gridlines: bool | None = None
    table_striped_rows: bool | None = None


class UpdateUserCommand(BaseModel):
    """All fields optional, only provided fields are updated."""

    username: str | None = None
    full_name: str | None = None
    email: EmailStr | None = None
    password: str | None = None
    # Proves the caller's own password when they change it themselves.
    current_password: str | None = None
    rfid: str | None = None

    is_active: bool | None = None
    is_shared_account: bool | None = None
    auth_provider: str | None = None
    member_ids: list[int] | None = None
    group_ids: list[int] | None = None
    permissions: list[str] | None = None

    language: Language | None = None
    date_format: DateFormat | None = None
    start_page: StartPage | None = None
    theme_preset: ThemePreset | None = None
    theme_surface: ThemeSurface | None = None
    theme_primary: ThemePrimary | None = None
    theme_dark_mode: bool | None = None
    button_flat_style: bool | None = None
    table_gridlines: bool | None = None
    table_striped_rows: bool | None = None


# ── Results (outbound) ────────────────────────────────────────────────


class UserPdmLinkResult(BaseModel):
    """One SOLIDWORKS PDM Web API user linked to this Glados user, see
    UserPdmLink's docstring. Read-only, set only through LinkPdmUsers."""

    pdm_user_id: int
    pdm_username: str
    linked_at: datetime


class UserResult(ResultBase):
    """What use cases return. Also the canonical shape for API responses."""

    username: str
    full_name: str
    email: str
    created: datetime
    language: Language
    date_format: DateFormat
    start_page: StartPage
    theme_preset: ThemePreset
    theme_surface: ThemeSurface
    theme_primary: ThemePrimary
    theme_dark_mode: bool
    button_flat_style: bool
    table_gridlines: bool
    table_striped_rows: bool
    # Whether an RFID tag is enrolled, never its stored lookup value. That
    # value is the HMAC of a low-entropy RFID UID, safe only while the app
    # secret stays unknown (see infrastructure/security/rfid.py), so it must
    # not leave the domain.
    rfid_configured: bool
    # SOLIDWORKS PDM Web API users linked to this account, set only
    # through LinkPdmUsers. Read-only: never settable through
    # UpdateUserCommand. Several entries are normal, see UserPdmLink's
    # docstring.
    pdm_links: list[UserPdmLinkResult]

    is_active: bool
    is_systemuser: bool
    is_service_account: bool
    is_shared_account: bool
    auth_provider: str
    member_ids: list[int]
    group_ids: list[int]
    # What the user may do: the direct grants plus every group's permissions.
    permissions: list[str]
    # The grants given to this user directly, what create and update set.
    direct_permissions: list[str]

    last_logged_in: datetime | None
    totp_enabled: bool

    has_avatar: bool


class PublicUserResult(ResultBase):
    """The non-sensitive part of a user, embedded wherever another resource
    references one (creator, orderer, receiver and so on). It carries no
    e-mail address, which only user administration may read."""

    username: str
    full_name: str
    has_avatar: bool


class UserSummaryResult(ResultBase):
    """The reduced view of a user that every signed-in user may read, for
    pickers and name lookups. E-mail, permissions, groups, 2FA state and the
    last login need read:settings and come only with UserResult. The account
    kind flags stay, because the pickers leave system, service and shared
    accounts out."""

    username: str
    full_name: str
    is_active: bool
    is_systemuser: bool
    is_service_account: bool
    is_shared_account: bool
    has_avatar: bool


class RfidIdentityResult(ResultBase):
    """Who an RFID tag belongs to, the minimal answer of the key surface's
    RFID lookup."""

    username: str
    full_name: str
