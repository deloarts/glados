"""
`User.date_format` is a display preference. These tests pin the two things
that matter about it: the preset set is closed (so the frontend can rely on
a known list), and it is validated at the HTTP boundary rather than reaching
the database as free text.
"""

import pytest
from pydantic import ValidationError

from src.modules.platform.adapters.inbound.api.schemas.user_schema import UserCreateRequest
from src.modules.platform.adapters.inbound.api.schemas.user_schema import UserUpdateRequest
from src.modules.platform.const import SERVER_DEFAULT_DATE_FORMAT
from src.modules.platform.domain.value_objects.date_format import DateFormat


class TestDateFormatValueObject:
    def test_default_is_iso(self):
        """ISO is what every date input in the UI already uses, and what the
        API itself speaks, so it is the least surprising default."""
        assert DateFormat.default() is DateFormat.ISO
        assert DateFormat.default().value == SERVER_DEFAULT_DATE_FORMAT

    def test_values_are_the_documented_preset_set(self):
        assert DateFormat.values() == [
            "iso",
            "dmy_dot",
            "dmy_slash",
            "mdy_slash",
            "d_mon_y",
        ]

    def test_is_a_str_enum_so_it_serializes_as_its_value(self):
        assert DateFormat.DMY_DOT == "dmy_dot"


class TestUserUpdateRequestDateFormat:
    def test_accepts_a_known_preset(self):
        assert UserUpdateRequest(date_format="dmy_dot").date_format is DateFormat.DMY_DOT

    def test_rejects_an_unknown_preset(self):
        with pytest.raises(ValidationError):
            UserUpdateRequest(date_format="dd.MM.yyyy")

    def test_rejects_a_free_form_pattern(self):
        """The whole point of presets over patterns, arbitrary strings never
        reach storage."""
        with pytest.raises(ValidationError):
            UserUpdateRequest(date_format="%Y/%m/%d")

    def test_empty_string_means_unset(self):
        """Mirrors the language/theme selects: the frontend sends "" for a
        cleared dropdown."""
        assert UserUpdateRequest(date_format="").date_format is None

    def test_omitting_it_leaves_it_none(self):
        assert UserUpdateRequest().date_format is None


class TestUserCreateRequestDateFormat:
    def _base(self) -> dict:
        return {
            "username": "newuser",
            "full_name": "New User",
            "email": "new@example.com",
            "password": "averysecurepassword",
        }

    def test_accepts_a_known_preset(self):
        req = UserCreateRequest(**self._base(), date_format="d_mon_y")
        assert req.date_format is DateFormat.D_MON_Y

    def test_rejects_an_unknown_preset(self):
        with pytest.raises(ValidationError):
            UserCreateRequest(**self._base(), date_format="nope")

    def test_defaults_to_none_so_the_use_case_applies_the_server_default(self):
        assert UserCreateRequest(**self._base()).date_format is None
