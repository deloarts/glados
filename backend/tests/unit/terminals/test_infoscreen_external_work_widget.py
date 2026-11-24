"""The stored config of the external work widget: its defaults, its bounds
and the layouts it knows."""

import pytest

from src.modules.operations.domain.errors import InvalidInfoscreenConfigError
from src.modules.operations.domain.value_objects.infoscreen import ExternalWorkWidget
from src.modules.operations.domain.value_objects.infoscreen import parse_widget
from src.modules.operations.domain.value_objects.infoscreen import widget_to_data


def test_a_bare_widget_reads_as_a_week_of_days_with_the_overdue_parts():
    widget = parse_widget({"type": "external_work"})

    assert widget == ExternalWorkWidget()
    assert (widget.horizon_days, widget.show_overdue, widget.layout) == (7, True, "days")
    assert widget.fabrication_method_ids == ()
    assert widget.only_with_supplier is False


def test_the_settings_round_trip_through_plain_data():
    raw = {
        "type": "external_work",
        "title": "Härterei",
        "horizon_days": 14,
        "show_overdue": False,
        "fabrication_method_ids": [6, 11],
        "only_with_supplier": True,
        "layout": "suppliers",
    }

    assert widget_to_data(parse_widget(raw)) == raw


@pytest.mark.parametrize(
    "raw",
    [
        {"type": "external_work", "layout": "rows"},
        {"type": "external_work", "horizon_days": 31},
        {"type": "external_work", "horizon_days": -1},
        {"type": "external_work", "fabrication_method_ids": [0]},
    ],
)
def test_an_unknown_layout_or_a_value_out_of_bounds_is_refused(raw):
    with pytest.raises(InvalidInfoscreenConfigError):
        parse_widget(raw)
