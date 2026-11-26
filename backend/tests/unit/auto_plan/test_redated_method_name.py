"""
The re-dated list names the method whose wait a predecessor takes: the last
step's, and for a MIXED position the last step done in house, not the
supplier's.
"""

from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.application.use_cases.production_schedule._redated import (
    _last_method_name,
)
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from tests.unit.test_response_time_days_buffer import make_position
from tests.unit.test_response_time_days_buffer import make_step


def _mixed_position():
    position = make_position(id=1, sequence=1)
    position.kind = LotPositionKind.MIXED
    gluing = make_step(1)
    gluing.sequence = 1
    gluing.role = StepRole.FABRICATION
    gluing.fabrication_method_name = LocalizedText({"enGB": "Gluing"})
    coating = make_step(1)
    coating.sequence = 2
    coating.role = StepRole.FABRICATION
    coating.fabrication_method_required_external = True
    coating.fabrication_method_name = LocalizedText({"enGB": "Coating"})
    position.steps = [gluing, coating]
    return position


def test_a_mixed_position_names_its_last_in_house_method():
    assert _last_method_name(_mixed_position()) == {"enGB": "Gluing"}


def test_an_internal_position_names_its_last_method():
    position = _mixed_position()
    position.kind = LotPositionKind.INTERNAL
    assert _last_method_name(position) == {"enGB": "Coating"}
