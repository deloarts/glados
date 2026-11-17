"""
Direct characterization tests for src/modules/fulfillment/domain/services/lot_rules.py: step
roles, position grouping and the structure guards. The statuses of a lot
and its positions are derived in src/domain/services/lifecycle/ and tested
there.
"""

from datetime import date

import pytest

from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.errors import LotPositionGroupingInvalidError
from src.modules.fulfillment.domain.errors import LotStructureLockedError
from src.modules.fulfillment.domain.services.lot_rules import LotRules
from src.modules.fulfillment.domain.services.lot_rules import assert_valid_step_role
from src.modules.fulfillment.domain.services.lot_rules import validate_position_grouping
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user

# ── assert_valid_step_role / validate_position_grouping (QA inspection) ─


def make_step(
    id: int,
    sequence: int,
    role: StepRole = StepRole.FABRICATION,
    fabrication_method_id: int | None = 1,
    inspection_method_id: int | None = None,
) -> LotStep:
    return LotStep(
        id=id,
        created=date(2026, 1, 1),
        note=None,
        estimated_setup_minutes=None,
        estimated_minutes_per_piece=None,
        sequence=sequence,
        creator_id=1,
        fabrication_method_id=fabrication_method_id,
        lot_id=1,
        position_id=1,
        source_process_id=None,
        role=role,
        inspection_method_id=inspection_method_id,
    )


class TestAssertValidStepRole:
    def test_valid_fabrication_combo(self):
        assert_valid_step_role(StepRole.FABRICATION.value, 1, None)

    def test_valid_inspection_combo(self):
        assert_valid_step_role(StepRole.INSPECTION.value, None, 1)

    def test_fabrication_without_method_raises(self):
        with pytest.raises(LotPositionGroupingInvalidError):
            assert_valid_step_role(StepRole.FABRICATION.value, None, None)

    def test_fabrication_with_inspection_method_raises(self):
        with pytest.raises(LotPositionGroupingInvalidError):
            assert_valid_step_role(StepRole.FABRICATION.value, 1, 1)

    def test_inspection_with_method_raises(self):
        with pytest.raises(LotPositionGroupingInvalidError):
            assert_valid_step_role(StepRole.INSPECTION.value, 1, 1)

    def test_inspection_without_inspection_method_raises(self):
        with pytest.raises(LotPositionGroupingInvalidError):
            assert_valid_step_role(StepRole.INSPECTION.value, None, None)


class TestValidatePositionGroupingInspectionIsolation:
    def test_inspection_step_cannot_share_a_group_with_a_fabrication_step(self):
        steps = [
            make_step(1, sequence=1),
            make_step(
                2,
                sequence=2,
                role=StepRole.INSPECTION,
                fabrication_method_id=None,
                inspection_method_id=1,
            ),
        ]
        with pytest.raises(LotPositionGroupingInvalidError):
            validate_position_grouping(steps, [[1, 2]])

    def test_inspection_step_cannot_share_a_group_with_another_inspection_step(self):
        steps = [
            make_step(
                1,
                sequence=1,
                role=StepRole.INSPECTION,
                fabrication_method_id=None,
                inspection_method_id=1,
            ),
            make_step(
                2,
                sequence=2,
                role=StepRole.INSPECTION,
                fabrication_method_id=None,
                inspection_method_id=2,
            ),
        ]
        with pytest.raises(LotPositionGroupingInvalidError):
            validate_position_grouping(steps, [[1, 2]])

    def test_inspection_step_alone_in_its_own_group_is_valid(self):
        steps = [
            make_step(1, sequence=1),
            make_step(
                2,
                sequence=2,
                role=StepRole.INSPECTION,
                fabrication_method_id=None,
                inspection_method_id=1,
            ),
        ]
        validate_position_grouping(steps, [[1], [2]])

    def test_fabrication_only_grouping_still_valid(self):
        steps = [
            make_step(1, sequence=1),
            make_step(2, sequence=2),
            make_step(3, sequence=3),
        ]
        validate_position_grouping(steps, [[1, 2], [3]])


# ── assert_can_edit_structure / assert_can_append_position (write:lots) ─


def _make_lot(status: LotStatus = LotStatus.DRAFT) -> ProductionLot:
    return ProductionLot(
        id=1,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        lot_number="LOT-1",
        quantity=5.0,
        status=status,
        priority=UrgencyClass.NORMAL,
        note=None,
        creator_id=1,
        made_item_id=1,
        project_id=1,
        input_demand_id=None,
    )


class TestAssertCanEditStructure:
    def test_rejects_missing_write_lots(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            LotRules.assert_can_edit_structure(actor, _make_lot())

    def test_permitted_actor_on_live_lot_is_allowed(self):
        actor = make_user(permissions=[Permission.WRITE_LOTS])
        LotRules.assert_can_edit_structure(actor, _make_lot())

    def test_still_rejects_terminal_lot_for_permitted_actor(self):
        """The new permission-first ordering must not swallow the 409: a
        permitted actor editing a terminal lot still gets LotStructureLocked."""
        actor = make_user(permissions=[Permission.WRITE_LOTS])
        with pytest.raises(LotStructureLockedError):
            LotRules.assert_can_edit_structure(actor, _make_lot(LotStatus.CANCELED))


class TestAssertCanAppendPosition:
    def test_rejects_missing_write_lots(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            LotRules.assert_can_append_position(actor, _make_lot())

    def test_permitted_actor_on_live_lot_is_allowed(self):
        actor = make_user(permissions=[Permission.WRITE_LOTS])
        LotRules.assert_can_append_position(actor, _make_lot())

    def test_still_rejects_terminal_lot_for_permitted_actor(self):
        actor = make_user(permissions=[Permission.WRITE_LOTS])
        with pytest.raises(LotStructureLockedError):
            LotRules.assert_can_append_position(actor, _make_lot(LotStatus.COMPLETED))
