"""
Unit tests for TestProductionOrderRulesPureFunctions. No database, no HTTP. All
dependencies replaced with in-memory fakes.
"""

from datetime import date

import pytest

from src.modules.catalogue.domain.errors import MachineCapabilityMismatchError
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.domain.errors import CompletionDateInvalidError
from src.modules.fulfillment.domain.errors import OperatorNotAssignedError
from src.modules.fulfillment.domain.errors import OperatorSelectionRequiredError
from src.modules.fulfillment.domain.errors import ProductionOrderCannotMergeError
from src.modules.fulfillment.domain.errors import ProductionOrderNoMachineAssignedError
from src.modules.fulfillment.domain.errors import ProductionOrderQuantityOverflowError
from src.modules.fulfillment.domain.errors import ProductionOrderSplitMismatchError
from src.modules.fulfillment.domain.services.production_order_rules import assert_can_merge
from src.modules.fulfillment.domain.services.production_order_rules import assert_capability_match
from src.modules.fulfillment.domain.services.production_order_rules import (
    assert_completion_date_allowed,
)
from src.modules.fulfillment.domain.services.production_order_rules import (
    assert_machine_or_pool_assigned,
)
from src.modules.fulfillment.domain.services.production_order_rules import (
    assert_pool_capability_match,
)
from src.modules.fulfillment.domain.services.production_order_rules import (
    assert_quantity_within_position,
)
from src.modules.fulfillment.domain.services.production_order_rules import (
    assert_split_sums_correctly,
)
from src.modules.fulfillment.domain.services.production_order_rules import is_position_fully_queued
from src.modules.fulfillment.domain.services.production_order_rules import position_is_manual
from src.modules.fulfillment.domain.services.production_order_rules import resolve_operator_id
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from tests.factories import make_user
from tests.unit.production_order._helpers import make_machine
from tests.unit.production_order._helpers import make_order
from tests.unit.production_order._helpers import make_pool
from tests.unit.production_order._helpers import make_step


class TestProductionOrderRulesPureFunctions:
    def test_assert_quantity_within_position_allows_exact_sum(self):
        assert_quantity_within_position(6.0, 4.0, 10.0)

    def test_assert_quantity_within_position_rejects_overflow(self):
        with pytest.raises(ProductionOrderQuantityOverflowError):
            assert_quantity_within_position(6.0, 5.0, 10.0)

    def test_is_position_fully_queued(self):
        orders = [make_order(id=1, quantity=6.0), make_order(id=2, quantity=4.0)]
        assert is_position_fully_queued(orders, 10.0) is True
        assert is_position_fully_queued(orders[:1], 10.0) is False

    def test_is_position_fully_queued_ignores_canceled_orders(self):
        orders = [
            make_order(id=1, quantity=6.0),
            make_order(id=2, quantity=4.0, status=ProductionOrderStatus.CANCELED),
        ]
        assert is_position_fully_queued(orders, 10.0) is False

    def test_assert_split_sums_correctly(self):
        assert_split_sums_correctly([6.0, 4.0], 10.0)
        with pytest.raises(ProductionOrderSplitMismatchError):
            assert_split_sums_correctly([6.0, 5.0], 10.0)
        with pytest.raises(ProductionOrderSplitMismatchError):
            assert_split_sums_correctly([10.0], 10.0)

    def test_assert_split_sums_correctly_rejects_zero_part(self):
        # A zero-quantity part sums correctly
        # (0.0 + 10.0 == 10.0) but produces a no-op split leg, which the
        # positivity check exists to catch.
        with pytest.raises(ProductionOrderSplitMismatchError, match="positive"):
            assert_split_sums_correctly([0.0, 10.0], 10.0)

    def test_assert_split_sums_correctly_rejects_negative_part(self):
        with pytest.raises(ProductionOrderSplitMismatchError, match="positive"):
            assert_split_sums_correctly([-2.0, 12.0], 10.0)

    def test_assert_can_merge_requires_same_machine_and_position(self):
        same = [
            make_order(id=1, machine_id=1, lot_position_id=1),
            make_order(id=2, machine_id=1, lot_position_id=1),
        ]
        assert_can_merge(same)
        different_machine = [make_order(id=1, machine_id=1), make_order(id=2, machine_id=2)]
        with pytest.raises(ProductionOrderCannotMergeError):
            assert_can_merge(different_machine)

    def test_resolve_operator_id_personal_account_defaults_to_self(self):
        actor = make_user(id=7)
        assert resolve_operator_id(actor, None) == 7
        assert resolve_operator_id(actor, 7) == 7

    def test_resolve_operator_id_personal_account_names_no_one_else(self):
        with pytest.raises(OperatorNotAssignedError):
            resolve_operator_id(make_user(id=7), 9)

    def test_resolve_operator_id_shared_account_requires_explicit(self):
        actor = make_user(id=7, is_shared_account=True, member_ids=[9])
        with pytest.raises(OperatorSelectionRequiredError):
            resolve_operator_id(actor, None)
        assert resolve_operator_id(actor, 9) == 9

    def test_resolve_operator_id_shared_account_rejects_non_member(self):
        actor = make_user(id=7, is_shared_account=True, member_ids=[9])
        with pytest.raises(OperatorNotAssignedError):
            resolve_operator_id(actor, 42)

    def test_resolve_operator_id_shared_account_with_no_members_rejects_any(self):
        actor = make_user(id=7, is_shared_account=True)
        with pytest.raises(OperatorNotAssignedError):
            resolve_operator_id(actor, 9)

    def test_position_is_manual_true_when_every_step_requires_no_machine(self):
        steps = [make_step(id=1), make_step(id=2)]
        for s in steps:
            s.fabrication_method_requires_machine = False
        assert position_is_manual(steps) is True

    def test_position_is_manual_false_when_any_step_requires_a_machine(self):
        manual_step = make_step(id=1)
        manual_step.fabrication_method_requires_machine = False
        machine_step = make_step(id=2)
        assert position_is_manual([manual_step, machine_step]) is False

    def test_position_is_manual_false_for_empty_steps(self):
        assert position_is_manual([]) is False

    def test_assert_machine_or_pool_assigned_rejects_machine_requiring_position_with_neither(self):
        with pytest.raises(ProductionOrderNoMachineAssignedError):
            assert_machine_or_pool_assigned([make_step(id=1)], None, None)

    def test_assert_machine_or_pool_assigned_allows_machine_requiring_position_with_machine(self):
        assert_machine_or_pool_assigned([make_step(id=1)], 1, None)  # no raise

    def test_assert_machine_or_pool_assigned_allows_machine_requiring_position_with_pool(self):
        assert_machine_or_pool_assigned([make_step(id=1)], None, 1)  # no raise

    def test_assert_machine_or_pool_assigned_allows_manual_position_with_neither(self):
        manual_step = make_step(id=1, fabrication_method_requires_machine=False)
        assert_machine_or_pool_assigned([manual_step], None, None)  # no raise

    def test_assert_machine_or_pool_assigned_allows_inspection_position_with_neither(self):
        inspection_step = make_step(
            id=1,
            fabrication_method_id=None,
            fabrication_method_requires_machine=False,
            role=StepRole.INSPECTION,
            inspection_method_id=1,
        )
        assert_machine_or_pool_assigned([inspection_step], None, None)  # no raise

    def test_assert_capability_match_ignores_manual_steps(self):
        """A machine covering only the machine-requiring step's method
        passes even though it doesn't cover the manual step's method, the
        manual step never has, and never will have, a capable machine."""
        manual_step = make_step(id=1, fabrication_method_id=2)
        manual_step.fabrication_method_requires_machine = False
        machine_step = make_step(id=2, fabrication_method_id=1)
        machine = make_machine(id=1, fabrication_method_ids=[1])
        assert_capability_match(machine, [manual_step, machine_step])  # no raise

    def test_assert_capability_match_rejects_pure_manual_position(self):
        """A position with no machine-requiring step at all must not be
        vacuously "covered" by an empty required-method set; it's queued
        machine-less instead (see assert_machine_or_pool_assigned)."""
        manual_step = make_step(id=1, fabrication_method_requires_machine=False)
        machine = make_machine(id=1, fabrication_method_ids=[])
        with pytest.raises(MachineCapabilityMismatchError):
            assert_capability_match(machine, [manual_step])

    def test_assert_capability_match_requires_qa_machine_for_inspection(self):
        inspection_step = make_step(
            id=1,
            fabrication_method_id=None,
            fabrication_method_requires_machine=False,
            role=StepRole.INSPECTION,
            inspection_method_id=1,
        )
        qa_machine = make_machine(id=1, is_qa_machine=True)
        assert_capability_match(qa_machine, [inspection_step])  # no raise
        with pytest.raises(MachineCapabilityMismatchError):
            assert_capability_match(make_machine(id=2), [inspection_step])

    def test_assert_capability_match_rejects_qa_machine_for_fabrication(self):
        # Even when the QA machine nominally lists the required method,
        # a dedicated measuring machine never takes fabrication work.
        step = make_step(fabrication_method_id=1)
        qa_machine = make_machine(id=1, fabrication_method_ids=[1], is_qa_machine=True)
        with pytest.raises(MachineCapabilityMismatchError):
            assert_capability_match(qa_machine, [step])

    def test_assert_pool_capability_match_rejects_inspection_position(self):
        inspection_step = make_step(
            id=1,
            fabrication_method_id=None,
            fabrication_method_requires_machine=False,
            role=StepRole.INSPECTION,
            inspection_method_id=1,
        )
        pool = make_pool(machines=[make_machine(id=1, is_qa_machine=True)])
        with pytest.raises(MachineCapabilityMismatchError):
            assert_pool_capability_match(pool, [inspection_step])

    def test_assert_pool_capability_match_ignores_manual_steps(self):
        manual_step = make_step(id=1, fabrication_method_id=2)
        manual_step.fabrication_method_requires_machine = False
        machine_step = make_step(id=2, fabrication_method_id=1)
        pool = make_pool(machines=[make_machine(id=1, fabrication_method_ids=[1])])
        assert_pool_capability_match(pool, [manual_step, machine_step])  # no raise

    def test_assert_pool_capability_match_rejects_pure_manual_position(self):
        manual_step = make_step(id=1, fabrication_method_requires_machine=False)
        pool = make_pool(machines=[make_machine(id=1, fabrication_method_ids=[])])
        with pytest.raises(MachineCapabilityMismatchError):
            assert_pool_capability_match(pool, [manual_step])

    def test_assert_pool_capability_match_uses_intersection_of_members(self):
        step = make_step(fabrication_method_id=1)
        pool = make_pool(
            machines=[
                make_machine(id=1, fabrication_method_ids=[1, 2]),
                make_machine(id=2, fabrication_method_ids=[1, 3]),
            ]
        )
        assert_pool_capability_match(pool, [step])  # 1 is in both -> no raise

    def test_assert_pool_capability_match_rejects_when_not_every_member_covers_it(self):
        step = make_step(fabrication_method_id=2)
        pool = make_pool(
            machines=[
                make_machine(id=1, fabrication_method_ids=[1, 2]),
                make_machine(id=2, fabrication_method_ids=[1, 3]),
            ]
        )
        with pytest.raises(MachineCapabilityMismatchError):
            assert_pool_capability_match(pool, [step])

    def test_assert_pool_capability_match_rejects_empty_pool(self):
        step = make_step(fabrication_method_id=1)
        pool = make_pool(machines=[])
        with pytest.raises(MachineCapabilityMismatchError):
            assert_pool_capability_match(pool, [step])


class TestCompletionDate:
    TODAY = date(2026, 10, 26)

    def test_today_and_the_start_day_are_allowed(self):
        assert_completion_date_allowed(self.TODAY, self.TODAY, date(2026, 10, 20))
        assert_completion_date_allowed(date(2026, 10, 20), self.TODAY, date(2026, 10, 20))
        assert_completion_date_allowed(date(2026, 1, 5), self.TODAY, None)

    def test_a_day_that_has_not_begun_is_refused(self):
        with pytest.raises(CompletionDateInvalidError):
            assert_completion_date_allowed(date(2026, 10, 27), self.TODAY, None)

    def test_a_day_before_the_order_was_started_is_refused(self):
        with pytest.raises(CompletionDateInvalidError):
            assert_completion_date_allowed(date(2026, 10, 19), self.TODAY, date(2026, 10, 20))
