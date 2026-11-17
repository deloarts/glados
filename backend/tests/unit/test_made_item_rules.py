"""
Direct unit coverage for src/modules/catalogue/domain/policies/made_item_rules.py's QA/
inspection step-role additions: assert_valid_step_role (mirrors
ck_made_item_process_role_method / ck_made_item_process_inspection_method)
and validate_process_grouping's rule that an inspection-role process can
never share a group with any other process. See test_lot_rules.py for
the LotStep-side mirror in lot_rules.py.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.catalogue.domain.entities.made_item_process import MadeItemProcess
from src.modules.catalogue.domain.errors import MadeItemProcessGroupingInvalidError
from src.modules.catalogue.domain.policies.made_item_rules import assert_valid_step_role
from src.modules.catalogue.domain.policies.made_item_rules import validate_process_grouping
from src.modules.catalogue.domain.value_objects.step_role import StepRole


def make_process(
    id: int,
    position: int,
    role: StepRole = StepRole.FABRICATION,
    fabrication_method_id: int | None = 1,
    inspection_method_id: int | None = None,
    group_index: int | None = None,
) -> MadeItemProcess:
    return MadeItemProcess(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        note=None,
        estimated_setup_minutes=None,
        estimated_minutes_per_piece=None,
        creator_id=1,
        fabrication_method_id=fabrication_method_id,
        made_item_id=1,
        position=position,
        group_index=group_index if group_index is not None else position,
        role=role,
        inspection_method_id=inspection_method_id,
    )


# ── assert_valid_step_role ──────────────────────────────────────────────


class TestAssertValidStepRole:
    def test_valid_fabrication_combo(self):
        assert_valid_step_role(StepRole.FABRICATION.value, 1, None)

    def test_valid_inspection_combo(self):
        assert_valid_step_role(StepRole.INSPECTION.value, None, 1)

    def test_fabrication_without_method_raises(self):
        with pytest.raises(MadeItemProcessGroupingInvalidError):
            assert_valid_step_role(StepRole.FABRICATION.value, None, None)

    def test_fabrication_with_inspection_method_raises(self):
        with pytest.raises(MadeItemProcessGroupingInvalidError):
            assert_valid_step_role(StepRole.FABRICATION.value, 1, 1)

    def test_inspection_with_method_raises(self):
        with pytest.raises(MadeItemProcessGroupingInvalidError):
            assert_valid_step_role(StepRole.INSPECTION.value, 1, 1)

    def test_inspection_without_inspection_method_raises(self):
        with pytest.raises(MadeItemProcessGroupingInvalidError):
            assert_valid_step_role(StepRole.INSPECTION.value, None, None)


# ── validate_process_grouping: inspection isolation rule ────────────────


class TestValidateProcessGroupingInspectionIsolation:
    def test_inspection_step_cannot_share_a_group_with_a_fabrication_step(self):
        processes = [
            make_process(1, position=1),
            make_process(
                2,
                position=2,
                role=StepRole.INSPECTION,
                fabrication_method_id=None,
                inspection_method_id=1,
            ),
        ]
        with pytest.raises(MadeItemProcessGroupingInvalidError):
            validate_process_grouping(processes, [[1, 2]])

    def test_inspection_step_cannot_share_a_group_with_another_inspection_step(self):
        processes = [
            make_process(
                1,
                position=1,
                role=StepRole.INSPECTION,
                fabrication_method_id=None,
                inspection_method_id=1,
            ),
            make_process(
                2,
                position=2,
                role=StepRole.INSPECTION,
                fabrication_method_id=None,
                inspection_method_id=2,
            ),
        ]
        with pytest.raises(MadeItemProcessGroupingInvalidError):
            validate_process_grouping(processes, [[1, 2]])

    def test_inspection_step_alone_in_its_own_group_is_valid(self):
        processes = [
            make_process(1, position=1),
            make_process(
                2,
                position=2,
                role=StepRole.INSPECTION,
                fabrication_method_id=None,
                inspection_method_id=1,
            ),
        ]
        validate_process_grouping(processes, [[1], [2]])

    def test_fabrication_only_grouping_still_valid(self):
        processes = [
            make_process(1, position=1),
            make_process(2, position=2),
            make_process(3, position=3),
        ]
        validate_process_grouping(processes, [[1, 2], [3]])
