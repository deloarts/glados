"""
Shared builders for domain entities that many test modules need. Unit and
integration tests import from here instead of writing their own copy, so a
new required entity field is added in one place.
"""

from datetime import UTC
from datetime import datetime
from functools import cache
from typing import Any

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.start_page import StartPage
from src.modules.platform.domain.value_objects.theme import ThemePreset
from src.modules.platform.domain.value_objects.theme import ThemePrimary
from src.modules.platform.domain.value_objects.theme import ThemeSurface
from src.modules.platform.infrastructure.security.hashing import get_hash

# The password every factory-built user can log in with, unless a test asks
# for another one through `make_user(password=...)`.
TEST_PASSWORD = "test-password"


@cache
def password_hash(password: str) -> str:
    """A bcrypt hash of `password`, computed once per test session.

    bcrypt costs about 0.17 s per call, and a fresh salt per user buys a test
    nothing, so every user built with the same password shares one digest.
    """
    return get_hash(password)


TEST_PASSWORD_HASH = password_hash(TEST_PASSWORD)


def make_user(
    *,
    id: int = 1,
    username: str = "testuser",
    email: str | None = None,
    full_name: str = "Test User",
    permissions: list[str] | None = None,
    password: str | None = None,
    is_active: bool = True,
    is_systemuser: bool = False,
    **overrides: Any,
) -> User:
    """A valid, active local user with no permissions.

    The email follows the username unless given. The stored hash matches
    `password`, which defaults to TEST_PASSWORD; pass `hashed_password` to
    store a value directly. Any other User field can be set by keyword.
    """
    if "hashed_password" not in overrides:
        overrides["hashed_password"] = password_hash(
            TEST_PASSWORD if password is None else password
        )
    fields: dict[str, Any] = {
        "created": datetime.now(UTC),
        "language": Language.enGB,
        "date_format": DateFormat.ISO,
        "start_page": StartPage.DASHBOARD,
        "theme_preset": ThemePreset.Aura,
        "theme_surface": ThemeSurface.glados,
        "theme_primary": ThemePrimary.glados,
        "theme_dark_mode": False,
        "button_flat_style": False,
        "table_gridlines": False,
        "table_striped_rows": False,
    }
    fields.update(overrides)
    return User(
        id=id,
        username=username,
        email=email if email is not None else f"{username}@example.com",
        full_name=full_name,
        permissions=permissions if permissions is not None else [],
        is_active=is_active,
        is_systemuser=is_systemuser,
        **fields,
    )
