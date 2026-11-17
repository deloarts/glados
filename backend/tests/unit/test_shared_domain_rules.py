"""
Unit tests for the small domain helpers several aggregates share: the
settings permission gate, the step role invariant, the demand ownership
checks, the production order status sets, the string enum base, the admin
settings audit entry factory, the live line status parser and the derived
quantities on production orders and order lines.
"""

from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from datetime import timedelta

import pytest

from src.modules.catalogue.domain.errors import MadeItemProcessGroupingInvalidError
from src.modules.catalogue.domain.policies.step_role_rules import assert_role_matches_methods
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.domain.errors import DemandItemAlreadyCanceledError
from src.modules.fulfillment.domain.errors import DemandItemAlreadyFulfilledError
from src.modules.fulfillment.domain.errors import DemandItemOfAnotherUserError
from src.modules.fulfillment.domain.errors import LotPositionGroupingInvalidError
from src.modules.fulfillment.domain.services.demand_ownership_rules import assert_can_cancel_demand
from src.modules.fulfillment.domain.services.demand_ownership_rules import assert_can_update_demand
from src.modules.fulfillment.domain.services.lot_rules import parse_live_line_status
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.production_status import (
    ACTIVE_PRODUCTION_ORDER_STATUSES,
)
from src.modules.fulfillment.domain.value_objects.production_status import (
    TERMINAL_PRODUCTION_ORDER_STATUSES,
)
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.domain.value_objects.theme import ThemePreset
from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum
from tests.factories import make_user
from tests.unit.test_production_lot_mapper import make_production_order
from tests.unit.test_quantity_edit_rules import make_line
from tests.unit.test_scrap_tag_resolver import make_completion

# ── Settings permission gate ──────────────────────────────────────────


def test_settings_rules_assert_can_read_requires_read_settings():
    SettingsRules.assert_can_read(make_user(permissions=[Permission.READ_SETTINGS]))
    with pytest.raises(
        InsufficientPermissionsError, match=r"^read:settings permission required\.$"
    ):
        SettingsRules.assert_can_read(make_user(permissions=[Permission.WRITE_SETTINGS]))


def test_settings_rules_assert_can_write_requires_write_settings():
    SettingsRules.assert_can_write(make_user(permissions=[Permission.WRITE_SETTINGS]))
    with pytest.raises(
        InsufficientPermissionsError, match=r"^write:settings permission required\.$"
    ):
        SettingsRules.assert_can_write(make_user(permissions=[Permission.READ_SETTINGS]))


# ── Step role ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("role", "fabrication_id", "inspection_id", "message"),
    [
        (StepRole.FABRICATION.value, None, None, "A fabrication-role step requires a "),
        (StepRole.FABRICATION.value, 1, 2, "A fabrication-role step must not have an "),
        (StepRole.INSPECTION.value, 1, 2, "An inspection-role step must not have a "),
        (StepRole.INSPECTION.value, None, None, "An inspection-role step requires an "),
        ("bogus", 1, None, "Unknown step role: 'bogus'."),
    ],
)
def test_assert_role_matches_methods_raises_the_given_error_with_the_noun(
    role, fabrication_id, inspection_id, message
):
    with pytest.raises(LotPositionGroupingInvalidError) as excinfo:
        assert_role_matches_methods(
            role, fabrication_id, inspection_id, error=LotPositionGroupingInvalidError, noun="step"
        )
    assert str(excinfo.value).startswith(message)


def test_assert_role_matches_methods_accepts_a_matching_role():
    assert_role_matches_methods(
        StepRole.FABRICATION.value,
        1,
        None,
        error=MadeItemProcessGroupingInvalidError,
        noun="process",
    )
    assert_role_matches_methods(
        StepRole.INSPECTION.value,
        None,
        1,
        error=MadeItemProcessGroupingInvalidError,
        noun="process",
    )


# ── Demand ownership ──────────────────────────────────────────────────


@dataclass
class _Demand:
    id: int
    status: str
    creator_id: int


def test_assert_can_update_demand_lets_a_manager_edit_any_demand():
    manager = make_user(permissions=[Permission.WRITE_DEMAND_ITEMS, Permission.MANAGE_DEMAND_ITEMS])
    assert_can_update_demand(manager, _Demand(id=3, status="fulfilled", creator_id=99))


@pytest.mark.parametrize(
    ("status", "creator_id", "error"),
    [
        ("fulfilled", 1, DemandItemAlreadyFulfilledError),
        ("canceled", 1, DemandItemAlreadyCanceledError),
        ("open", 99, DemandItemOfAnotherUserError),
    ],
)
def test_assert_can_update_demand_refuses_a_plain_writer(status, creator_id, error):
    writer = make_user(permissions=[Permission.WRITE_DEMAND_ITEMS])
    with pytest.raises(error):
        assert_can_update_demand(writer, _Demand(id=3, status=status, creator_id=creator_id))


def test_assert_can_update_demand_needs_write_demand_items():
    with pytest.raises(InsufficientPermissionsError):
        assert_can_update_demand(
            make_user(permissions=[]), _Demand(id=3, status="open", creator_id=1)
        )


def test_assert_can_cancel_demand_refuses_a_finished_demand_even_for_a_manager():
    manager = make_user(permissions=[Permission.MANAGE_DEMAND_ITEMS])
    with pytest.raises(DemandItemAlreadyFulfilledError):
        assert_can_cancel_demand(manager, _Demand(id=3, status="fulfilled", creator_id=1))
    with pytest.raises(DemandItemAlreadyCanceledError, match=r"is already canceled\.$"):
        assert_can_cancel_demand(manager, _Demand(id=3, status="canceled", creator_id=1))


def test_assert_can_cancel_demand_limits_a_non_manager_to_own_demands():
    assert_can_cancel_demand(make_user(permissions=[]), _Demand(id=3, status="open", creator_id=1))
    with pytest.raises(DemandItemOfAnotherUserError):
        assert_can_cancel_demand(
            make_user(permissions=[]), _Demand(id=3, status="open", creator_id=99)
        )


# ── Status sets and enums ─────────────────────────────────────────────


def test_production_order_status_sets_partition_the_enum():
    assert {"completed", "canceled"} == TERMINAL_PRODUCTION_ORDER_STATUSES
    assert {"queued", "in_progress", "paused"} == ACTIVE_PRODUCTION_ORDER_STATUSES
    assert (
        set(ProductionOrderStatus.values())
        == TERMINAL_PRODUCTION_ORDER_STATUSES | ACTIVE_PRODUCTION_ORDER_STATUSES
    )


def test_str_value_enum_lists_values_in_definition_order():
    class _Colour(StrValueEnum):
        RED = "red"
        GREEN = "green"

    assert _Colour.values() == ["red", "green"]
    assert _Colour.RED == "red"
    assert ThemePreset.values()[0] == ThemePreset.default().value


# ── Audit entry factory ───────────────────────────────────────────────


def test_admin_settings_audit_entry_by_actor_stamps_actor_and_time():
    actor = make_user(permissions=[Permission.WRITE_SETTINGS])

    entry = AdminSettingsAuditEntry.by_actor(actor, settings_domain="mail", summary="Changed.")

    assert entry.id == 0
    assert entry.changed_by_id == actor.id
    assert entry.changed_by_username == actor.username
    assert entry.settings_domain == "mail"
    assert entry.summary == "Changed."
    assert datetime.now(UTC) - entry.changed_at < timedelta(seconds=5)
    assert entry.changed_at.tzinfo is not None


# ── Live line status and derived quantities ──────────────────────────


def test_parse_live_line_status_reads_known_statuses_only():
    assert parse_live_line_status("ordered") is OrderItemStatus.ORDERED
    assert parse_live_line_status(None) is None
    assert parse_live_line_status("") is None
    assert parse_live_line_status("not-a-status") is None


def test_production_order_pieces_processed_sums_its_completions():
    order = make_production_order(1, position_id=1, machine_id=None)
    assert order.pieces_processed == 0.0

    order.completions = [
        make_completion(1, quantity_scrap=2.0),
        make_completion(2, quantity_scrap=3.5),
    ]

    assert order.pieces_processed == 5.5


def test_order_item_quantity_settled_adds_delivered_and_lost():
    assert make_line(delivered=4.0, lost=1.5).quantity_settled == 5.5
