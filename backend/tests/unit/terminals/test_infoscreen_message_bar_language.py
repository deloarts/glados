"""Validation of the newer infoscreen settings: the `company_name` bar item,
the message widget's `none` severity and its alignment, and the screen
language."""

from typing import Any

import pytest

from src.modules.operations.domain.errors import InvalidInfoscreenConfigError
from src.modules.operations.domain.services import infoscreen_rules
from src.modules.operations.domain.value_objects.infoscreen import MessageWidget
from src.modules.operations.domain.value_objects.infoscreen import parse_bar
from src.modules.operations.domain.value_objects.infoscreen import parse_widget
from src.modules.operations.domain.value_objects.infoscreen import widget_to_data


def test_infoscreen_bar_accepts_the_company_name_once() -> None:
    bar = parse_bar({"left": ["logo", "company_name"], "right": ["clock"]})
    assert bar.left == ("logo", "company_name")
    with pytest.raises(InvalidInfoscreenConfigError, match="more than once"):
        parse_bar({"left": ["company_name"], "right": ["company_name"]})


def test_infoscreen_message_reads_defaults_from_an_older_config() -> None:
    widget = parse_widget({"type": "message", "text": "# Safety\n\n- Wear ear protection"})
    assert isinstance(widget, MessageWidget)
    assert (widget.severity, widget.text_align, widget.vertical_align) == (
        "info",
        "left",
        "middle",
    )
    assert widget.text == "# Safety\n\n- Wear ear protection"


def test_infoscreen_message_takes_none_severity_and_alignment() -> None:
    raw = {
        "type": "message",
        "title": None,
        "text": "Welcome",
        "severity": "none",
        "text_align": "center",
        "vertical_align": "bottom",
    }
    widget = parse_widget(raw)
    assert widget_to_data(widget) == raw


@pytest.mark.parametrize(
    ("raw", "fragment"),
    [
        ({"severity": "loud"}, "severity"),
        ({"text_align": "justify"}, "text_align"),
        ({"vertical_align": "center"}, "vertical_align"),
        ({"text": "x" * 2001}, "at most 2000"),
    ],
)
def test_infoscreen_message_refuses_invalid_values(raw: dict[str, Any], fragment: str) -> None:
    with pytest.raises(InvalidInfoscreenConfigError, match=fragment):
        parse_widget({"type": "message", "text": "Hello", **raw})


def test_infoscreen_language_must_be_an_app_locale_or_empty() -> None:
    settings: dict[str, Any] = {
        "color_mode": "dark",
        "theme_preset": None,
        "primary_color": None,
        "rotation_seconds": 30,
    }
    # Must not raise: both app locales and the tenant default are valid.
    for language in ("enGB", "deAT", None):
        infoscreen_rules.assert_settings_valid(**settings, language=language)
    with pytest.raises(InvalidInfoscreenConfigError, match="language"):
        infoscreen_rules.assert_settings_valid(**settings, language="frFR")
