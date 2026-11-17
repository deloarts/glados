"""
`User.start_page` is where the frontend routes a user right after login,
when no explicit `redirect` was given. These tests pin the two things that
matter about it, mirroring test_user_date_format.py: the preset set is
closed (so the frontend can rely on a known list, matching the sidebar's
top-level entries), and it is validated at the HTTP boundary rather than
reaching the database as free text. Unlike date_format (and
language), there is no tenant-wide default on AdminGeneralSettings; this
is per-user only, see StartPage's own docstring.
"""

import pytest
from pydantic import ValidationError

from src.modules.platform.adapters.inbound.api.schemas.user_schema import UserCreateRequest
from src.modules.platform.adapters.inbound.api.schemas.user_schema import UserUpdateRequest
from src.modules.platform.const import SERVER_DEFAULT_START_PAGE
from src.modules.platform.domain.value_objects.start_page import StartPage


class TestStartPageValueObject:
    def test_default_is_dashboard(self):
        assert StartPage.default() is StartPage.DASHBOARD
        assert StartPage.default().value == SERVER_DEFAULT_START_PAGE

    def test_values_mirror_the_sidebars_top_level_entries(self):
        assert StartPage.values() == [
            "dashboard",
            "todo",
            "workspace",
            "catalogue",
            "procurement",
            "production",
            "resources",
            "tools",
        ]

    def test_is_a_str_enum_so_it_serializes_as_its_value(self):
        assert StartPage.PRODUCTION == "production"


class TestUserUpdateRequestStartPage:
    def test_accepts_a_known_page(self):
        assert UserUpdateRequest(start_page="production").start_page is StartPage.PRODUCTION

    def test_rejects_an_unknown_page(self):
        with pytest.raises(ValidationError):
            UserUpdateRequest(start_page="not-a-page")

    def test_empty_string_means_unset(self):
        """Mirrors the language/theme/date_format selects: the frontend
        sends "" for a cleared dropdown."""
        assert UserUpdateRequest(start_page="").start_page is None

    def test_omitting_it_leaves_it_none(self):
        assert UserUpdateRequest().start_page is None


class TestUserCreateRequestStartPage:
    def _base(self) -> dict:
        return {
            "username": "newuser",
            "full_name": "New User",
            "email": "new@example.com",
            "password": "averysecurepassword",
        }

    def test_accepts_a_known_page(self):
        req = UserCreateRequest(**self._base(), start_page="workspace")
        assert req.start_page is StartPage.WORKSPACE

    def test_rejects_an_unknown_page(self):
        with pytest.raises(ValidationError):
            UserCreateRequest(**self._base(), start_page="nope")

    def test_defaults_to_none_so_the_use_case_applies_the_server_default(self):
        assert UserCreateRequest(**self._base()).start_page is None
