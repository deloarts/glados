"""
The tenant's default timezone is a free-form IANA name rather than an Enum
(the valid set is the platform's tz database), so the general settings
validate it through the Timezone value object. These tests hold that guard
in place, and that the user schemas no longer carry a timezone of their own.
"""

from src.modules.platform.adapters.inbound.api.schemas.user_schema import UserCreateRequest
from src.modules.platform.adapters.inbound.api.schemas.user_schema import UserResponse
from src.modules.platform.adapters.inbound.api.schemas.user_schema import UserUpdateRequest
from src.modules.platform.domain.value_objects.timezone import Timezone


class TestTimezoneValueObject:
    def test_default_is_a_real_zone(self):
        assert Timezone.is_valid(Timezone.default())

    def test_known_zones_validate(self):
        assert Timezone.is_valid("Europe/Vienna")
        assert Timezone.is_valid("America/New_York")
        assert Timezone.is_valid("UTC")

    def test_junk_is_rejected(self):
        assert not Timezone.is_valid("Middle/Earth")
        assert not Timezone.is_valid("CEST")
        assert not Timezone.is_valid("+02:00")
        assert not Timezone.is_valid("")

    def test_values_is_sorted_and_non_empty(self):
        values = Timezone.values()
        assert values
        assert values == sorted(values)


class TestUserSchemasCarryNoTimezone:
    """The whole app reads days in the tenant's timezone, so a user has none."""

    def test_no_user_schema_declares_a_timezone(self):
        for schema in (UserCreateRequest, UserUpdateRequest, UserResponse):
            assert "timezone" not in schema.model_fields
