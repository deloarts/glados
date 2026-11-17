"""
Pure domain entity. No SQLAlchemy, no Pydantic, no FastAPI.
This is the in-memory representation of a user once loaded from any storage backend.
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime

from src.modules.platform.domain.value_objects.auth_provider import AuthProvider
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.start_page import StartPage
from src.modules.platform.domain.value_objects.theme import ThemePreset
from src.modules.platform.domain.value_objects.theme import ThemePrimary
from src.modules.platform.domain.value_objects.theme import ThemeSurface
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class User(Entity):
    # Identity
    username: str
    full_name: str
    email: str
    created: datetime

    # Auth
    hashed_password: str

    # Role flags
    is_active: bool
    is_systemuser: bool

    # Permissions granted to this user directly. What the user may do is
    # effective_permissions, which adds the permissions of their groups.
    permissions: list[str]

    # Preferences
    language: Language
    # Display-only: it never affects what is stored or what the API accepts.
    date_format: DateFormat
    # Where the frontend routes this user right after login when no explicit
    # `redirect` was given. Per-user only, there is deliberately no
    # tenant-wide default, unlike language and date_format above, see
    # domain/value_objects/start_page.py.
    start_page: StartPage
    theme_preset: ThemePreset
    theme_surface: ThemeSurface
    theme_primary: ThemePrimary
    theme_dark_mode: bool
    button_flat_style: bool
    table_gridlines: bool
    table_striped_rows: bool

    # Session tracking (defaulted, must stay after all non-defaulted fields)
    token_version: int = 0
    last_logged_in: datetime | None = None
    # When a password login last proved this account's password, for a
    # directory account against the directory itself. A passkey login never
    # asks the directory, so for those accounts this bounds how long a
    # passkey works without a fresh password (login_policy).
    password_verified_at: datetime | None = None

    # 2FA
    totp_secret: str | None = None
    totp_enabled: bool = False

    # Avatar
    avatar_key: str | None = None

    # Service accounts (API keys), non-interactive identity, never logs in
    # via password/RFID, permissions are whatever its backing API key was granted.
    is_service_account: bool = False

    # Shop-floor shared LDAP login, when True, shop-floor actions
    # (production order start/pause/completion) require selecting the
    # actual operator; personal accounts default the operator to self.
    is_shared_account: bool = False

    # Operators eligible to act under this shared account. Meaningless on
    # personal accounts; empty on a shared account means it cannot act at
    # all until an admin assigns members (strict, no implicit fallback).
    member_ids: list[int] = field(default_factory=list)

    # Which credential store answers for this user. Admin-only, forced back
    # to the target's current value in UserRules.resolve_permission_flags, so
    # nobody can move themselves onto (or off) the directory.
    auth_provider: str = AuthProvider.LOCAL

    # Deterministic HMAC of the RFID tag (see
    # infrastructure/security/rfid.py), the only stored form of the tag and
    # the key of the O(1) lookup in SqlAlchemyUserRepository.get_by_rfid.
    # None when the user has no tag. Server-managed: exposed in no command
    # DTO, a command carries the plain tag instead.
    rfid_lookup: str | None = None

    # The groups this user belongs to and the union of their permissions.
    # Only the user repository loads them. A user resolved as the relation
    # of another row, such as the creator of an order, carries none, which
    # is harmless because such a user is never permission checked.
    group_ids: list[int] = field(default_factory=list)
    group_permissions: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Permission helpers
    # ------------------------------------------------------------------

    @property
    def effective_permissions(self) -> list[str]:
        """The direct grants plus everything the user's groups grant, sorted.
        There are no denials, so the union is all there is to it."""
        return sorted(set(self.permissions) | set(self.group_permissions))

    def has_permission(self, permission: str) -> bool:
        """System users pass all checks; everyone else must hold the
        permission directly or through one of their groups."""
        if self.is_systemuser:
            return True
        return permission in self.permissions or permission in self.group_permissions

    def is_self(self, other: "User") -> bool:
        return self.id == other.id
