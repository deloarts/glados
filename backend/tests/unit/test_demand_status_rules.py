"""
The rule that decides who may set a demand's status by hand, shared by the
bought, made and source item demand families. A user needs
write:demand_items; without manage:demand_items only the creator may change
the status, and never to FULFILLED or CANCELED. Pure domain, no fakes.
"""

from dataclasses import dataclass
from datetime import UTC
from datetime import datetime

import pytest

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.domain.errors import DemandItemOfAnotherUserError
from src.modules.fulfillment.domain.services.demand_status_rules import (
    assert_can_change_demand_status,
)
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.domain.value_objects.start_page import StartPage
from src.modules.platform.domain.value_objects.theme import ThemePreset
from src.modules.platform.domain.value_objects.theme import ThemePrimary
from src.modules.platform.domain.value_objects.theme import ThemeSurface

CREATOR_ID = 1
REVERSIBLE_TARGETS = ["open", "allocated", "ordered"]
IRREVERSIBLE_TARGETS = ["fulfilled", "canceled"]
ALL_TARGETS = REVERSIBLE_TARGETS + IRREVERSIBLE_TARGETS
WRITE = [Permission.WRITE_DEMAND_ITEMS]
MANAGE = [Permission.WRITE_DEMAND_ITEMS, Permission.MANAGE_DEMAND_ITEMS]


@dataclass
class _Demand:
    id: int = 7
    creator_id: int = CREATOR_ID


def _user(id: int, permissions: list[str], *, is_systemuser: bool = False) -> User:
    return User(
        id=id,
        username=f"user{id}",
        full_name=f"User {id}",
        email=f"user{id}@example.com",
        created=datetime(2026, 1, 1, tzinfo=UTC),
        hashed_password="not-a-real-hash",
        is_active=True,
        is_systemuser=is_systemuser,
        permissions=permissions,
        language=Language.enGB,
        date_format=DateFormat.ISO,
        start_page=StartPage.DASHBOARD,
        theme_preset=ThemePreset.Aura,
        theme_surface=ThemeSurface.glados,
        theme_primary=ThemePrimary.glados,
        theme_dark_mode=False,
        button_flat_style=False,
        table_gridlines=False,
        table_striped_rows=False,
    )


@pytest.mark.parametrize("target", ALL_TARGETS)
def test_demand_status_rule_refuses_a_user_without_write_permission(target: str) -> None:
    # Being the creator does not help without write:demand_items.
    read_only_creator = _user(CREATOR_ID, [])
    with pytest.raises(InsufficientPermissionsError) as raised:
        assert_can_change_demand_status(read_only_creator, _Demand(), target)
    assert raised.type is InsufficientPermissionsError


@pytest.mark.parametrize("target", REVERSIBLE_TARGETS)
def test_demand_status_rule_lets_the_creator_make_a_reversible_change(target: str) -> None:
    # A None-returning validator: passing means it did not raise.
    assert_can_change_demand_status(_user(CREATOR_ID, WRITE), _Demand(), target)


@pytest.mark.parametrize("target", IRREVERSIBLE_TARGETS)
def test_demand_status_rule_keeps_irreversible_targets_from_the_creator(target: str) -> None:
    with pytest.raises(InsufficientPermissionsError, match="manage:demand_items") as raised:
        assert_can_change_demand_status(_user(CREATOR_ID, WRITE), _Demand(), target)
    assert raised.type is InsufficientPermissionsError


@pytest.mark.parametrize("target", ALL_TARGETS)
def test_demand_status_rule_refuses_another_users_demand(target: str) -> None:
    with pytest.raises(DemandItemOfAnotherUserError):
        assert_can_change_demand_status(_user(2, WRITE), _Demand(), target)


@pytest.mark.parametrize("target", ALL_TARGETS)
def test_demand_status_rule_lets_a_manager_change_any_demand(target: str) -> None:
    # A None-returning validator: passing means it did not raise.
    assert_can_change_demand_status(_user(3, MANAGE), _Demand(), target)


@pytest.mark.parametrize("target", ALL_TARGETS)
def test_demand_status_rule_needs_write_permission_even_with_manage(target: str) -> None:
    manage_only = _user(3, [Permission.MANAGE_DEMAND_ITEMS])
    with pytest.raises(InsufficientPermissionsError) as raised:
        assert_can_change_demand_status(manage_only, _Demand(), target)
    assert raised.type is InsufficientPermissionsError


@pytest.mark.parametrize("target", ALL_TARGETS)
def test_demand_status_rule_lets_the_system_user_change_any_demand(target: str) -> None:
    # A None-returning validator: passing means it did not raise.
    assert_can_change_demand_status(_user(4, [], is_systemuser=True), _Demand(), target)


@pytest.mark.parametrize(
    "status_enum", [BoughtItemDemandStatus, MadeItemDemandStatus, SourceItemDemandStatus]
)
def test_demand_status_rule_reads_every_familys_terminal_statuses_as_irreversible(
    status_enum: type[BoughtItemDemandStatus | MadeItemDemandStatus | SourceItemDemandStatus],
) -> None:
    creator = _user(CREATOR_ID, WRITE)
    for terminal in (status_enum.FULFILLED, status_enum.CANCELED):
        with pytest.raises(InsufficientPermissionsError):
            assert_can_change_demand_status(creator, _Demand(), terminal.value)
    for reversible in (status_enum.OPEN, status_enum.ALLOCATED, status_enum.ORDERED):
        assert_can_change_demand_status(creator, _Demand(), reversible.value)
