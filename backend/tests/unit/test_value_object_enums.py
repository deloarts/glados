"""
Coverage for the small `str, Enum` value objects whose `default()` /
`values()` classmethods had no test at all, theme, language,
user_role, order_file_category. These are trivial individually, but
every one of them is a contract the API schemas and the frontend rely
on (a renamed member or changed default is a breaking wire change), so
they're worth pinning down.
"""

import dataclasses

import pytest

from src.modules.fulfillment.domain.value_objects.order_file_category import OrderFileCategory
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.theme import ThemePreset
from src.modules.platform.domain.value_objects.theme import ThemePrimary
from src.modules.platform.domain.value_objects.theme import ThemeSurface
from src.modules.platform.domain.value_objects.user_role import UserRole

# ── Theme ─────────────────────────────────────────────────────────────


class TestThemePreset:
    def test_default_is_aura(self):
        assert ThemePreset.default() == ThemePreset.Aura

    def test_values_lists_every_member_value(self):
        assert ThemePreset.values() == ["Aura", "Lara", "Material", "Nora"]

    def test_members_are_plain_strings(self):
        assert ThemePreset.Aura == "Aura"

    def test_default_is_a_member_of_values(self):
        assert ThemePreset.default().value in ThemePreset.values()


class TestThemeSurface:
    def test_default_is_glados(self):
        assert ThemeSurface.default() == ThemeSurface.glados

    def test_values_lists_every_member_value(self):
        assert ThemeSurface.values() == ["glados", "slate", "gray", "zinc", "neutral", "stone"]

    def test_default_is_a_member_of_values(self):
        assert ThemeSurface.default().value in ThemeSurface.values()


class TestThemePrimary:
    def test_default_is_glados(self):
        assert ThemePrimary.default() == ThemePrimary.glados

    def test_values_has_all_20_palettes(self):
        assert len(ThemePrimary.values()) == 20

    def test_values_starts_with_the_custom_palettes(self):
        assert ThemePrimary.values()[:3] == ["glados", "noir", "soul"]

    def test_default_is_a_member_of_values(self):
        assert ThemePrimary.default().value in ThemePrimary.values()


# ── Language ──────────────────────────────────────────────────────────


class TestLanguage:
    def test_default_is_engb(self):
        assert Language.default() == Language.enGB

    def test_values_lists_both_locales(self):
        assert Language.values() == ["deAT", "enGB"]

    def test_default_is_a_member_of_values(self):
        assert Language.default().value in Language.values()


# ── OrderFileCategory ─────────────────────────────────────────────────


class TestOrderFileCategory:
    def test_all_six_categories_exist_with_expected_wire_values(self):
        assert OrderFileCategory.PROPOSAL == "proposal"
        assert OrderFileCategory.ORDER_CONFIRMATION == "order_confirmation"
        assert OrderFileCategory.DELIVERY_NOTE == "delivery_note"
        assert OrderFileCategory.INVOICE == "invoice"
        assert OrderFileCategory.GENERAL == "general"
        assert OrderFileCategory.PICTURE == "picture"

    def test_has_exactly_six_members(self):
        assert len(list(OrderFileCategory)) == 6


# ── UserRole ──────────────────────────────────────────────────────────


class _FakeUser:
    """Structural stand-in for User, UserRole.from_user only reads
    is_systemuser/permissions, so a full User entity isn't needed."""

    def __init__(self, is_systemuser: bool, permissions: list[str]):
        self.is_systemuser = is_systemuser
        self.permissions = permissions


class TestUserRole:
    def test_from_user_snapshots_permissions_as_a_tuple(self):
        role = UserRole.from_user(_FakeUser(False, ["a", "b"]))  # type: ignore[arg-type]
        assert role.permissions == ("a", "b")
        assert role.is_systemuser is False

    def test_snapshot_is_immutable_against_later_user_mutation(self):
        user = _FakeUser(False, ["a"])
        role = UserRole.from_user(user)  # type: ignore[arg-type]
        user.permissions.append("b")
        assert role.permissions == ("a",)

    def test_has_returns_true_for_a_granted_permission(self):
        role = UserRole(is_systemuser=False, permissions=("read", "write"))
        assert role.has("read") is True

    def test_has_returns_false_for_a_missing_permission(self):
        role = UserRole(is_systemuser=False, permissions=("read",))
        assert role.has("write") is False

    def test_system_user_has_every_permission_including_unknown_ones(self):
        role = UserRole(is_systemuser=True, permissions=())
        assert role.has("anything-at-all") is True

    def test_role_is_frozen(self):
        role = UserRole(is_systemuser=False, permissions=())
        with pytest.raises(dataclasses.FrozenInstanceError):
            role.is_systemuser = True  # type: ignore[misc]
