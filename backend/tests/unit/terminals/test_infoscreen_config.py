"""Validation of infoscreen pages and widget configs, the screen settings,
and the rules the feed applies to the data it gathers."""

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from typing import Any

import pytest

from src.modules.fulfillment.domain.services.scheduling.machine_calendar import (
    build_machine_calendar,
)
from src.modules.fulfillment.domain.value_objects.work_interval import WorkInterval
from src.modules.operations.domain.errors import InvalidInfoscreenConfigError
from src.modules.operations.domain.services import infoscreen_rules
from src.modules.operations.domain.value_objects.infoscreen import DEFAULT_FOOTER
from src.modules.operations.domain.value_objects.infoscreen import DEFAULT_HEADER
from src.modules.operations.domain.value_objects.infoscreen import ClockWidget
from src.modules.operations.domain.value_objects.infoscreen import InfoscreenBar
from src.modules.operations.domain.value_objects.infoscreen import MachineBoardWidget
from src.modules.operations.domain.value_objects.infoscreen import bar_to_data
from src.modules.operations.domain.value_objects.infoscreen import pages_to_data
from src.modules.operations.domain.value_objects.infoscreen import parse_bar
from src.modules.operations.domain.value_objects.infoscreen import parse_pages
from src.modules.platform.domain.entities.admin_settings.banner import AdminBannerSettings
from src.modules.platform.domain.entities.tenant_holiday import TenantHoliday
from src.modules.platform.domain.value_objects.announcement_severity import AnnouncementSeverity
from src.modules.platform.domain.value_objects.holiday_category import HolidayCategory
from src.read.domain.services import infoscreen_feed_rules as rules

NOW = datetime(2026, 10, 30, 10, 0, tzinfo=UTC)

_EVERY_WIDGET: list[dict[str, Any]] = [
    {"type": "machine_board", "title": "Hall", "machine_ids": [1, 2, 2], "pool_ids": [3]},
    {"type": "lots_due", "horizon_days": 14, "pool_ids": [], "show_customer": True},
    {"type": "late_lots", "show_customer": False},
    {"type": "qa_queue"},
]


def test_infoscreen_pages_round_trip_through_plain_data() -> None:
    raw = [
        {"layout": "grid_2x2", "slots": _EVERY_WIDGET},
        {
            "layout": "two_columns",
            "slots": [
                {"type": "deliveries_expected", "horizon_days": 3},
                {"type": "message", "text": "Safety first", "severity": "warning"},
            ],
        },
        {"layout": "main_side", "slots": [{"type": "clock", "show_next_holiday": True}, None]},
        {"layout": "full", "slots": [None]},
    ]
    pages = parse_pages(raw)
    board = pages[0].slots[0]
    assert isinstance(board, MachineBoardWidget)
    assert board.machine_ids == (1, 2)
    assert board.next_count == 3
    clock = pages[2].slots[0]
    assert isinstance(clock, ClockWidget) and clock.show_date is True
    assert parse_pages(pages_to_data(pages)) == pages


@pytest.mark.parametrize(
    ("page", "fragment"),
    [
        ({"layout": "full", "slots": [None, None]}, "has 1 slot"),
        ({"layout": "grid_2x2", "slots": [None]}, "has 4 slot"),
        ({"layout": "diagonal", "slots": [None]}, "layout must be one of"),
        ({"layout": "full", "slots": [{"type": "radar"}]}, "unknown widget type"),
        ({"layout": "full", "slots": [{"type": "machine_board", "next_count": 11}]}, "next_count"),
        ({"layout": "full", "slots": [{"type": "lots_due", "horizon_days": 0}]}, "horizon_days"),
        (
            {"layout": "full", "slots": [{"type": "deliveries_expected", "horizon_days": 31}]},
            "horizon_days",
        ),
        ({"layout": "full", "slots": [{"type": "message", "text": "  "}]}, "needs a text"),
        (
            {"layout": "full", "slots": [{"type": "message", "text": "x", "severity": "red"}]},
            "severity",
        ),
        ({"layout": "full", "slots": [{"type": "machine_board", "machine_ids": [0]}]}, "positive"),
        ({"layout": "full", "slots": [{"type": "late_lots", "show_customer": "yes"}]}, "true"),
    ],
)
def test_infoscreen_invalid_pages_are_refused(page: dict[str, Any], fragment: str) -> None:
    with pytest.raises(InvalidInfoscreenConfigError, match=fragment):
        parse_pages([page])


def test_infoscreen_settings_validation() -> None:
    infoscreen_rules.assert_settings_valid(
        color_mode="dark", theme_preset=None, primary_color=None, rotation_seconds=30
    )
    infoscreen_rules.assert_settings_valid(
        color_mode="light", theme_preset="Nora", primary_color="emerald", rotation_seconds=600
    )
    for bad in (
        {"color_mode": "sepia"},
        {"theme_preset": "Bootstrap"},
        {"primary_color": " "},
        {"rotation_seconds": 9},
        {"rotation_seconds": 601},
    ):
        fields: dict[str, Any] = {
            "color_mode": "dark",
            "theme_preset": None,
            "primary_color": None,
            "rotation_seconds": 30,
            **bad,
        }
        with pytest.raises(InvalidInfoscreenConfigError):
            infoscreen_rules.assert_settings_valid(**fields)


def test_infoscreen_machine_state_priorities() -> None:
    assert rules.machine_state(down=True, running=True, working_now=True) == "down"
    assert rules.machine_state(down=False, running=True, working_now=False) == "running"
    assert rules.machine_state(down=False, running=False, working_now=False) == "closed"
    assert rules.machine_state(down=False, running=False, working_now=True) == "idle"


def test_infoscreen_working_window_includes_the_start_and_excludes_the_end() -> None:
    calendar = build_machine_calendar({4: (WorkInterval(480, 480),)}, None, {})  # Friday 08-16
    friday = datetime(2026, 10, 30, 8, 0, tzinfo=UTC)
    assert rules.is_working_at(calendar, friday)
    assert rules.is_working_at(calendar, friday + timedelta(hours=7, minutes=59))
    assert not rules.is_working_at(calendar, friday + timedelta(hours=8))
    assert not rules.is_working_at(calendar, friday - timedelta(minutes=1))


def test_infoscreen_banner_visibility() -> None:
    banner = AdminBannerSettings(
        id=1,
        enabled=True,
        text="Fire drill at 11",
        severity=AnnouncementSeverity.WARNING,
        shows_from=NOW - timedelta(hours=1),
        shows_until=NOW + timedelta(hours=1),
        dismissable=True,
        updated_at=NOW,
    )
    assert rules.banner_visible(banner, NOW)
    assert not rules.banner_visible(banner, NOW + timedelta(hours=2))
    assert not rules.banner_visible(banner, NOW - timedelta(hours=2))
    banner.enabled = False
    assert not rules.banner_visible(banner, NOW)


def test_infoscreen_next_holiday_includes_one_running_today() -> None:
    def holiday(id: int, start: date, end: date, name: str) -> TenantHoliday:
        return TenantHoliday(
            id=id,
            created=NOW,
            changed=None,
            changes=[],
            name=name,
            category=HolidayCategory.PUBLIC_HOLIDAY,
            start_date=start,
            end_date=end,
            creator_id=1,
        )

    today = date(2026, 10, 30)
    past = holiday(1, date(2026, 10, 1), date(2026, 10, 1), "Past")
    running = holiday(2, date(2026, 10, 29), date(2026, 10, 31), "Running")
    later = holiday(3, date(2026, 11, 1), date(2026, 11, 1), "All Saints")
    assert rules.next_holiday([past, later, running], today) is running
    assert rules.next_holiday([past, later], today) is later
    assert rules.next_holiday([past], today) is None


@pytest.mark.parametrize(
    ("layout", "slots"),
    [
        ("full", 1),
        ("two_columns", 2),
        ("main_side", 2),
        ("grid_2x2", 4),
        ("two_rows", 2),
        ("three_rows", 3),
        ("grid_2x3", 6),
        ("grid_3x2", 6),
    ],
)
def test_infoscreen_every_layout_takes_exactly_its_slot_count(layout: str, slots: int) -> None:
    assert parse_pages([{"layout": layout, "slots": [None] * slots}])[0].layout == layout
    for wrong in (slots - 1, slots + 1):
        with pytest.raises(InvalidInfoscreenConfigError, match=f"has {slots} slot"):
            parse_pages([{"layout": layout, "slots": [None] * wrong}])


def test_infoscreen_bar_parses_three_areas_in_order_and_round_trips() -> None:
    bar = parse_bar(
        {
            "left": ["logo", "app_name"],
            "center": ["text", "next_holiday"],
            "right": ["date", "clock"],
            "text": "  Hall 3  ",
        }
    )
    assert bar.left == ("logo", "app_name")
    assert bar.center == ("text", "next_holiday")
    assert bar.right == ("date", "clock")
    assert bar.text == "Hall 3"
    assert bar.shows_next_holiday
    assert parse_bar(bar_to_data(bar)) == bar
    assert parse_bar({"left": [], "text": " "}) == InfoscreenBar()
    assert InfoscreenBar(left=("logo", "title"), right=("clock",)) == DEFAULT_HEADER
    assert InfoscreenBar(right=("last_updated",)) == DEFAULT_FOOTER
    assert not DEFAULT_HEADER.shows_next_holiday


@pytest.mark.parametrize(
    ("raw", "fragment"),
    [
        ({"left": ["logo", "logo"]}, "more than once"),
        ({"left": ["logo"], "right": ["logo"]}, "more than once"),
        ({"center": ["clock"], "right": ["clock"]}, "more than once"),
        ({"left": ["weather"]}, "items must be among"),
        ({"right": "logo"}, "right must be a list"),
        ({"left": ["text"], "text": "x" * 201}, "at most 200"),
        ({"left": ["text"], "text": 5}, "must be text"),
    ],
)
def test_infoscreen_invalid_bars_are_refused(raw: dict[str, Any], fragment: str) -> None:
    with pytest.raises(InvalidInfoscreenConfigError, match=fragment):
        parse_bar(raw, "Header")


def test_infoscreen_days_overdue() -> None:
    today = date(2026, 10, 30)
    assert rules.days_overdue(date(2026, 10, 22), today) == 8
    assert rules.days_overdue(today, today) is None
    assert rules.days_overdue(date(2026, 11, 2), today) is None


def test_infoscreen_clock_reads_defaults_from_an_older_config_and_checks_its_style() -> None:
    [page] = parse_pages([{"layout": "full", "slots": [{"type": "clock", "show_date": False}]}])
    clock = page.slots[0]
    assert isinstance(clock, ClockWidget)
    assert (clock.show_seconds, clock.style, clock.show_date) == (False, "digital", False)
    [page] = parse_pages(
        [{"layout": "full", "slots": [{"type": "clock", "style": "binary", "show_seconds": True}]}]
    )
    assert isinstance(page.slots[0], ClockWidget) and page.slots[0].style == "binary"
    with pytest.raises(InvalidInfoscreenConfigError, match="style"):
        parse_pages([{"layout": "full", "slots": [{"type": "clock", "style": "sundial"}]}])
