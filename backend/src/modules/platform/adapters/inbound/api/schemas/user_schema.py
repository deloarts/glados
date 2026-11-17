"""
Pydantic models for the HTTP layer only. These are what the client sends
and receives. They never cross into the application or domain layer.
Mapped to/from application DTOs in the endpoint functions.
"""

from datetime import datetime
from typing import Literal

from fastapi import Query
from pydantic import BaseModel
from pydantic import EmailStr
from pydantic import Field
from pydantic import field_validator
from pydantic import model_validator

from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageParams
from src.modules.platform.const import SERVER_DEFAULT_AUTH_PROVIDER
from src.modules.platform.domain.value_objects.auth_provider import AuthProvider
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.start_page import StartPage
from src.modules.platform.domain.value_objects.theme import ThemePreset
from src.modules.platform.domain.value_objects.theme import ThemePrimary
from src.modules.platform.domain.value_objects.theme import ThemeSurface
from src.modules.platform.infrastructure.config.settings import cfg
from src.modules.platform.ports.outbound.repositories.user_repository import UserFilterDto

# ── Request schemas ───────────────────────────────────────────────────


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=1)
    full_name: str = Field(..., min_length=1)
    email: EmailStr
    # Conditional on auth_provider, so the length rule lives in the validator
    # below rather than in Field(): a directory account must NOT carry one.
    password: str | None = None
    rfid: str | None = Field(None, min_length=8)

    is_active: bool = True
    is_shared_account: bool = False
    auth_provider: str = SERVER_DEFAULT_AUTH_PROVIDER
    member_ids: list[int] = []
    group_ids: list[int] = []
    # The grants given to this user directly; groups add their own on top.
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

    @field_validator(
        "language",
        "date_format",
        "start_page",
        "theme_preset",
        "theme_surface",
        "theme_primary",
        "auth_provider",
        mode="before",
    )
    @classmethod
    def empty_enum_to_none(cls, v: object) -> object:
        return None if v == "" else v

    @model_validator(mode="after")
    def check_password_matches_auth_provider(self) -> "UserCreateRequest":
        """A local account needs a password; a directory account must not have
        one.

        Rejecting rather than ignoring the directory case: an admin who typed a
        password deserves to be told it would never have worked, instead of
        walking away believing the account has a local fallback it does not.
        """
        if self.auth_provider == AuthProvider.LDAP:
            if self.password:
                raise ValueError(
                    "A directory-authenticated account cannot have a local password. "
                    "Leave the password empty; the directory holds the credential."
                )
            return self
        if not self.password or len(self.password) < cfg.security.min_pw_len:
            raise ValueError(f"Password must be at least {cfg.security.min_pw_len} characters.")
        return self


class UserUpdateRequest(BaseModel):
    username: str | None = Field(None, min_length=1)
    full_name: str | None = Field(None, min_length=1)
    email: EmailStr | None = None
    password: str | None = Field(None, min_length=cfg.security.min_pw_len)
    # Required when a user changes their own password, never when an
    # administrator sets someone else's (CurrentPasswordRequiredError).
    current_password: str | None = None
    rfid: str | None = Field(None, min_length=8)

    is_active: bool | None = None
    is_shared_account: bool | None = None
    auth_provider: str | None = None
    member_ids: list[int] | None = None
    group_ids: list[int] | None = None
    # The grants given to this user directly; groups add their own on top.
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

    @field_validator(
        "language",
        "date_format",
        "start_page",
        "theme_preset",
        "theme_surface",
        "theme_primary",
        "auth_provider",
        mode="before",
    )
    @classmethod
    def empty_enum_to_none(cls, v: object) -> object:
        return None if v == "" else v


# ── Response schemas ──────────────────────────────────────────────────


class UserPdmLinkResponse(ResponseModel):
    """One SOLIDWORKS PDM Web API user linked to this Glados user. Read-only
    here; an admin sets the links in the PDM user reconciliation dialog."""

    pdm_user_id: int
    pdm_username: str
    linked_at: datetime


class UserResponse(EntityResponse):
    """What the API returns to clients."""

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
    rfid_configured: bool  # whether an RFID tag is enrolled, never the hash
    # SOLIDWORKS PDM Web API users linked to this account, set only
    # through LinkPdmUsers (admin console). Read-only here: never settable
    # through UserUpdateRequest. Several entries are normal, one Glados
    # user may release under more than one vault account.
    pdm_links: list[UserPdmLinkResponse]

    is_active: bool
    is_systemuser: bool
    # An API key's identity, which takes its permissions from the key and
    # never joins a group.
    is_service_account: bool
    is_shared_account: bool
    auth_provider: Literal["local", "ldap"]
    member_ids: list[int]
    group_ids: list[int]
    # What the user may do: the direct grants plus every group's permissions.
    permissions: list[str]
    # The grants given to this user directly, what create and update set.
    direct_permissions: list[str]

    last_logged_in: datetime | None
    totp_enabled: bool

    has_avatar: bool


class PublicUserResponse(EntityResponse):
    """A user embedded in another resource (creator, orderer and so on).
    No e-mail address: that belongs to user administration."""

    username: str
    full_name: str
    has_avatar: bool


class UserSummaryResponse(EntityResponse):
    """The reduced user view every signed-in user may read, see
    UserSummaryResult."""

    username: str
    full_name: str
    is_active: bool
    is_systemuser: bool
    is_service_account: bool
    is_shared_account: bool
    has_avatar: bool


# ── Filter params ─────────────────────────────────────────────────────


class UserFilterParams(PageParams):
    search: str | None = Query(default=None, description="Fuzzy search across all text columns")
    id: int | None = Query(default=None)
    username: str | None = Query(default=None)
    full_name: str | None = Query(default=None)
    email: str | None = Query(default=None)
    is_active: bool | None = Query(default=None)
    is_service_account: bool | None = Query(default=None)
    order_by: Literal["id", "username", "full_name", "email", "created"] | None = Query(
        default=None
    )
    order_dir: Literal["asc", "desc"] | None = Query(default=None)

    def to_dto(self) -> UserFilterDto:
        return UserFilterDto(**self.model_dump())


class UserDirectoryFilterParams(PageParams):
    """The directory's filters, without the e-mail column."""

    search: str | None = Query(default=None, description="Fuzzy search on username and name")
    id: int | None = Query(default=None)
    username: str | None = Query(default=None)
    full_name: str | None = Query(default=None)
    is_active: bool | None = Query(default=None)
    is_service_account: bool | None = Query(default=None)
    order_by: Literal["id", "username", "full_name"] | None = Query(default=None)
    order_dir: Literal["asc", "desc"] | None = Query(default=None)

    def to_dto(self) -> UserFilterDto:
        return UserFilterDto(**self.model_dump(), search_includes_email=False)
