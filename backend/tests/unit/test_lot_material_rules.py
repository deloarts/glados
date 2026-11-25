"""
Tests for src/modules/fulfillment/domain/services/lot_material_rules.py: who
brings the material of a lot's first position, and what a change of that
position does to the lot's source approval status and raw material demand.
"""

from dataclasses import dataclass
from datetime import UTC
from datetime import datetime

import pytest

from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.services.lifecycle.facts import LotPositionFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import PositionLineFacts
from src.modules.fulfillment.domain.services.lot_material_rules import DemandAction
from src.modules.fulfillment.domain.services.lot_material_rules import MaterialDecision
from src.modules.fulfillment.domain.services.lot_material_rules import MaterialSupply
from src.modules.fulfillment.domain.services.lot_material_rules import capped_to_in_house
from src.modules.fulfillment.domain.services.lot_material_rules import decide_material
from src.modules.fulfillment.domain.services.lot_material_rules import first_position
from src.modules.fulfillment.domain.services.lot_material_rules import first_position_supply
from src.modules.fulfillment.domain.services.lot_material_rules import in_house_need
from src.modules.fulfillment.domain.services.lot_material_rules import initial_status
from src.modules.fulfillment.domain.services.lot_material_rules import lot_supply
from src.modules.fulfillment.domain.services.lot_material_rules import position_supplier_share
from src.modules.fulfillment.domain.services.lot_material_rules import predicts_supplier_material
from src.modules.fulfillment.domain.services.lot_material_rules import supplier_share
from src.modules.fulfillment.domain.services.lot_material_rules import tracks_material
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.domain.value_objects.source_approval_status import SourceApprovalStatus

_S = SourceApprovalStatus


@dataclass
class _Step:
    role: StepRole
    fabrication_method_required_external: bool


def _external() -> _Step:
    return _Step(StepRole.FABRICATION, True)


def _in_house() -> _Step:
    return _Step(StepRole.FABRICATION, False)


def _lot(
    *,
    source_item_id: int | None = None,
    source_bought_item_id: int | None = None,
    source_made_item_id: int | None = None,
) -> ProductionLot:
    return ProductionLot(
        id=1,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=None,
        changes=[],
        lot_number="LOT-1",
        quantity=10.0,
        status=LotStatus.DRAFT,
        priority=UrgencyClass.NORMAL,
        note=None,
        creator_id=1,
        made_item_id=1,
        project_id=1,
        input_demand_id=None,
        source_item_id=source_item_id,
        source_bought_item_id=source_bought_item_id,
        source_made_item_id=source_made_item_id,
    )


def _line(status: OrderItemStatus, quantity: float, delivered: float = 0.0) -> PositionLineFacts:
    return PositionLineFacts(status=status, quantity=quantity, delivered=delivered)


class TestPredictsSupplierMaterial:
    def test_every_step_required_external(self) -> None:
        assert predicts_supplier_material([_external(), _external()])

    def test_one_in_house_step_keeps_it_ours(self) -> None:
        assert not predicts_supplier_material([_external(), _in_house()])

    def test_an_inspection_is_done_in_house(self) -> None:
        assert not predicts_supplier_material([_Step(StepRole.INSPECTION, False)])

    def test_no_steps_predict_nothing(self) -> None:
        assert not predicts_supplier_material([])


class TestTracksMaterial:
    def test_source_item(self) -> None:
        assert tracks_material(_lot(source_item_id=3))

    def test_bought_item(self) -> None:
        assert tracks_material(_lot(source_bought_item_id=3))

    def test_rework_lot_is_left_alone(self) -> None:
        assert not tracks_material(_lot(source_made_item_id=3))

    def test_no_source(self) -> None:
        assert not tracks_material(_lot())


class TestFirstPositionSupply:
    @pytest.mark.parametrize(
        ("kind", "predicted", "supply"),
        [
            (LotPositionKind.EXTERNAL, False, MaterialSupply.SUPPLIER),
            (LotPositionKind.EXTERNAL, True, MaterialSupply.SUPPLIER),
            (LotPositionKind.MIXED, True, MaterialSupply.SHARED),
            (LotPositionKind.INTERNAL, True, MaterialSupply.OURS),
            (LotPositionKind.UNASSIGNED, True, MaterialSupply.SUPPLIER_EXPECTED),
            (LotPositionKind.UNASSIGNED, False, MaterialSupply.OURS),
        ],
    )
    def test_kind_wins_over_the_prediction(
        self, kind: LotPositionKind, predicted: bool, supply: MaterialSupply
    ) -> None:
        assert first_position_supply(kind, predicted=predicted) is supply


class TestSupplierShare:
    def test_live_lines_count_and_a_canceled_one_does_not(self) -> None:
        facts = LotPositionFacts(
            quantity=10.0,
            line=_line(OrderItemStatus.ORDERED, 4.0),
            closed_lines=(_line(OrderItemStatus.DELIVERED, 2.0, 2.0),),
            orders=(),
            lot_canceled=False,
        )
        assert supplier_share(facts) == pytest.approx(6.0)

    def test_canceled_line_holds_nothing(self) -> None:
        facts = LotPositionFacts(
            quantity=10.0,
            line=_line(OrderItemStatus.CANCELED, 4.0),
            orders=(),
            lot_canceled=False,
        )
        assert supplier_share(facts) == 0.0


class TestInHouseNeed:
    def test_ours_needs_the_whole_position(self) -> None:
        assert in_house_need(MaterialSupply.OURS, 10.0, 4.0) == 10.0

    def test_shared_needs_what_the_supplier_does_not_hold(self) -> None:
        assert in_house_need(MaterialSupply.SHARED, 10.0, 4.0) == pytest.approx(6.0)

    def test_shared_never_below_zero(self) -> None:
        assert in_house_need(MaterialSupply.SHARED, 10.0, 12.0) == 0.0

    @pytest.mark.parametrize("supply", [MaterialSupply.SUPPLIER, MaterialSupply.SUPPLIER_EXPECTED])
    def test_supplier_needs_nothing(self, supply: MaterialSupply) -> None:
        assert in_house_need(supply, 10.0, 0.0) == 0.0


class TestInitialStatus:
    def test_expected_supplier_awaits_the_first_step(self) -> None:
        status = initial_status(
            MaterialSupply.SUPPLIER_EXPECTED, approval_required=True, source_is_item=True
        )
        assert status is _S.AWAITING_FIRST_STEP

    def test_supplier_sources_it(self) -> None:
        status = initial_status(
            MaterialSupply.SUPPLIER, approval_required=True, source_is_item=True
        )
        assert status is _S.SUPPLIER_SOURCED

    def test_ours_with_approval_on_is_pending_for_a_source_item(self) -> None:
        status = initial_status(MaterialSupply.OURS, approval_required=True, source_is_item=True)
        assert status is _S.PENDING

    def test_ours_with_a_bought_item_needs_no_approval(self) -> None:
        status = initial_status(MaterialSupply.OURS, approval_required=True, source_is_item=False)
        assert status is _S.NOT_REQUIRED

    def test_ours_with_approval_off(self) -> None:
        status = initial_status(MaterialSupply.OURS, approval_required=False, source_is_item=True)
        assert status is _S.NOT_REQUIRED


def _decide(
    supply: MaterialSupply,
    current: SourceApprovalStatus,
    live: float | None,
    need: float,
    *,
    approval_required: bool = False,
) -> MaterialDecision:
    return decide_material(
        supply,
        current=current,
        live_demand_quantity=live,
        need=need,
        approval_required=approval_required,
        source_is_item=True,
    )


class TestDecideMaterial:
    @pytest.mark.parametrize("current", list(SourceApprovalStatus))
    def test_supplier_settles_a_live_demand_whatever_was_decided(
        self, current: SourceApprovalStatus
    ) -> None:
        decision = _decide(MaterialSupply.SUPPLIER, current, 10.0, 0.0)
        assert decision == MaterialDecision(_S.SUPPLIER_SOURCED, DemandAction.SETTLE)

    def test_supplier_without_a_demand_only_moves_the_status(self) -> None:
        decision = _decide(MaterialSupply.SUPPLIER, _S.PENDING, None, 0.0)
        assert decision == MaterialDecision(_S.SUPPLIER_SOURCED)

    def test_unassigned_again_with_the_prediction_awaits_the_first_step(self) -> None:
        decision = _decide(MaterialSupply.SUPPLIER_EXPECTED, _S.SUPPLIER_SOURCED, None, 0.0)
        assert decision == MaterialDecision(_S.AWAITING_FIRST_STEP)

    def test_in_house_after_supplier_demands_at_once_with_approval_off(self) -> None:
        decision = _decide(MaterialSupply.OURS, _S.SUPPLIER_SOURCED, None, 10.0)
        assert decision == MaterialDecision(_S.NOT_REQUIRED, DemandAction.CREATE, 10.0)

    def test_in_house_after_supplier_waits_for_approval_when_on(self) -> None:
        decision = _decide(
            MaterialSupply.OURS, _S.AWAITING_FIRST_STEP, None, 10.0, approval_required=True
        )
        assert decision == MaterialDecision(_S.PENDING)

    def test_shared_after_supplier_demands_the_in_house_share(self) -> None:
        decision = _decide(MaterialSupply.SHARED, _S.SUPPLIER_SOURCED, None, 6.0)
        assert decision == MaterialDecision(_S.NOT_REQUIRED, DemandAction.CREATE, 6.0)

    def test_shared_shrinks_the_live_demand(self) -> None:
        decision = _decide(MaterialSupply.SHARED, _S.APPROVED, 10.0, 6.0)
        assert decision == MaterialDecision(_S.APPROVED, DemandAction.RESIZE, 6.0)

    def test_ours_again_grows_the_live_demand_back(self) -> None:
        decision = _decide(MaterialSupply.OURS, _S.NOT_REQUIRED, 6.0, 10.0)
        assert decision == MaterialDecision(_S.NOT_REQUIRED, DemandAction.RESIZE, 10.0)

    def test_a_fitting_demand_stays(self) -> None:
        decision = _decide(MaterialSupply.OURS, _S.APPROVED, 10.0, 10.0)
        assert decision == MaterialDecision(_S.APPROVED)

    def test_a_demand_a_user_ended_is_not_recreated(self) -> None:
        decision = _decide(MaterialSupply.OURS, _S.NOT_REQUIRED, None, 10.0)
        assert decision == MaterialDecision(_S.NOT_REQUIRED)

    def test_a_rejected_source_stays_rejected(self) -> None:
        decision = _decide(MaterialSupply.OURS, _S.REJECTED, None, 10.0, approval_required=True)
        assert decision == MaterialDecision(_S.REJECTED)

    def test_nothing_left_in_house_settles(self) -> None:
        decision = _decide(MaterialSupply.SHARED, _S.NOT_REQUIRED, 10.0, 0.0)
        assert decision == MaterialDecision(_S.NOT_REQUIRED, DemandAction.SETTLE)


def _position(
    sequence: int,
    kind: LotPositionKind,
    *,
    steps: list[_Step] | None = None,
    line: tuple[OrderItemStatus, float] | None = None,
    closed: float = 0.0,
) -> LotPosition:
    position = LotPosition(
        id=sequence,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=None,
        changes=[],
        sequence=sequence,
        kind=kind,
        status=LotPositionStatus.PENDING,
        quantity=10.0,
        quantity_completed=0.0,
        note=None,
        creator_id=1,
        lot_id=1,
    )
    position.steps = steps or []  # type: ignore[assignment]
    if line is not None:
        position.order_item_status, position.order_item_quantity = line
    position.closed_lines_quantity = closed
    return position


def _lot_with(*positions: LotPosition) -> ProductionLot:
    lot = _lot(source_item_id=3)
    lot.positions = list(positions)
    return lot


class TestFirstPosition:
    def test_lowest_sequence(self) -> None:
        lot = _lot_with(
            _position(2, LotPositionKind.INTERNAL), _position(1, LotPositionKind.EXTERNAL)
        )
        assert first_position(lot).sequence == 1  # type: ignore[union-attr]

    def test_none_without_positions(self) -> None:
        assert first_position(_lot_with()) is None


class TestPositionSupplierShare:
    def test_live_line_and_closed_lines(self) -> None:
        position = _position(
            1, LotPositionKind.MIXED, line=(OrderItemStatus.ORDERED, 4.0), closed=2.0
        )
        assert position_supplier_share(position) == pytest.approx(6.0)

    def test_canceled_line_holds_nothing(self) -> None:
        position = _position(1, LotPositionKind.MIXED, line=(OrderItemStatus.CANCELED, 4.0))
        assert position_supplier_share(position) == 0.0


class TestLotSupply:
    def test_external_first_position(self) -> None:
        lot = _lot_with(_position(1, LotPositionKind.EXTERNAL))
        assert lot_supply(lot, enabled=True) is MaterialSupply.SUPPLIER

    def test_predicted_from_the_steps_while_unassigned(self) -> None:
        lot = _lot_with(_position(1, LotPositionKind.UNASSIGNED, steps=[_external()]))
        assert lot_supply(lot, enabled=True) is MaterialSupply.SUPPLIER_EXPECTED

    def test_setting_off_is_always_ours(self) -> None:
        lot = _lot_with(_position(1, LotPositionKind.EXTERNAL))
        assert lot_supply(lot, enabled=False) is MaterialSupply.OURS

    def test_rework_lot_is_ours(self) -> None:
        lot = _lot(source_made_item_id=3)
        lot.positions = [_position(1, LotPositionKind.EXTERNAL)]
        assert lot_supply(lot, enabled=True) is MaterialSupply.OURS


class TestCappedToInHouse:
    def test_mixed_caps_to_the_in_house_share(self) -> None:
        lot = _lot_with(_position(1, LotPositionKind.MIXED, line=(OrderItemStatus.ORDERED, 4.0)))
        assert capped_to_in_house(lot, MaterialSupply.SHARED, 10.0) == pytest.approx(6.0)

    def test_ours_keeps_the_quantity(self) -> None:
        lot = _lot_with(_position(1, LotPositionKind.INTERNAL))
        assert capped_to_in_house(lot, MaterialSupply.OURS, 12.0) == 12.0

    def test_a_smaller_quantity_stays(self) -> None:
        lot = _lot_with(_position(1, LotPositionKind.MIXED, line=(OrderItemStatus.ORDERED, 4.0)))
        assert capped_to_in_house(lot, MaterialSupply.SHARED, 3.0) == 3.0
