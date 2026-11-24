"""Value objects of an infoscreen: its colour mode, theme preset, page
layouts, the header and footer bars, and the widget config of each slot.

Pages are stored as one JSON column. `parse_pages` turns that JSON (or a
request already dumped to plain data) into these value objects and refuses
anything the rules do not allow, so a stored screen is always valid;
`pages_to_data` turns them back into plain data. A slot holds one widget
config or nothing.
"""

from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import field
from enum import unique
from typing import Any
from typing import Final
from typing import cast

from src.modules.operations.domain.errors import InvalidInfoscreenConfigError
from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class InfoscreenColorMode(StrValueEnum):
    DARK = "dark"
    LIGHT = "light"

    @classmethod
    def default(cls) -> "InfoscreenColorMode":
        return cls.DARK


@unique
class InfoscreenThemePreset(StrValueEnum):
    """The theme presets the frontend ships; None on a screen means the
    tenant default."""

    AURA = "Aura"
    LARA = "Lara"
    MATERIAL = "Material"
    NORA = "Nora"


@unique
class InfoscreenLayout(StrValueEnum):
    FULL = "full"
    TWO_COLUMNS = "two_columns"
    GRID_2X2 = "grid_2x2"
    MAIN_SIDE = "main_side"
    TWO_ROWS = "two_rows"
    THREE_ROWS = "three_rows"
    # Two columns by three rows, for portrait screens.
    GRID_2X3 = "grid_2x3"
    # Three columns by two rows.
    GRID_3X2 = "grid_3x2"


@unique
class InfoscreenBarItem(StrValueEnum):
    """What a header or footer bar can show. `logo`, `app_name` and
    `company_name` come from the public branding, `last_updated` is the
    feed's generation time and `text` is the bar's own text."""

    LOGO = "logo"
    # The tenant's app name from the branding settings.
    APP_NAME = "app_name"
    # The tenant's company name from the branding settings.
    COMPANY_NAME = "company_name"
    TITLE = "title"
    CLOCK = "clock"
    DATE = "date"
    NEXT_HOLIDAY = "next_holiday"
    LAST_UPDATED = "last_updated"
    TEXT = "text"


@unique
class InfoscreenWidgetType(StrValueEnum):
    MACHINE_BOARD = "machine_board"
    LOTS_DUE = "lots_due"
    LATE_LOTS = "late_lots"
    QA_QUEUE = "qa_queue"
    DELIVERIES_EXPECTED = "deliveries_expected"
    MESSAGE = "message"
    CLOCK = "clock"
    WEATHER = "weather"
    PRODUCTS = "products"
    PROJECTS = "projects"
    MACHINE_DETAIL = "machine_detail"
    EXTERNAL_WORK = "external_work"


@unique
class InfoscreenExternalWorkLayout(StrValueEnum):
    # Grouped by the day the parts must leave at the latest.
    DAYS = "days"
    # One lane per supplier with its next send-out day and how much is ready.
    SUPPLIERS = "suppliers"


@unique
class InfoscreenClockStyle(StrValueEnum):
    DIGITAL = "digital"
    ANALOGUE = "analogue"
    BINARY = "binary"


@unique
class InfoscreenTextAlign(StrValueEnum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


@unique
class InfoscreenVerticalAlign(StrValueEnum):
    TOP = "top"
    MIDDLE = "middle"
    BOTTOM = "bottom"


@unique
class InfoscreenMessageSeverity(StrValueEnum):
    """How a message widget is tinted; `none` shows it without a colour."""

    NONE = "none"
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    DANGER = "danger"


# One slot per layout position.
SLOTS_PER_LAYOUT: Final[dict[str, int]] = {
    InfoscreenLayout.FULL.value: 1,
    InfoscreenLayout.TWO_COLUMNS.value: 2,
    InfoscreenLayout.GRID_2X2.value: 4,
    InfoscreenLayout.MAIN_SIDE.value: 2,
    InfoscreenLayout.TWO_ROWS.value: 2,
    InfoscreenLayout.THREE_ROWS.value: 3,
    InfoscreenLayout.GRID_2X3.value: 6,
    InfoscreenLayout.GRID_3X2.value: 6,
}

ROTATION_SECONDS_MIN: Final = 10
ROTATION_SECONDS_MAX: Final = 600
ROTATION_SECONDS_DEFAULT: Final = 30
MAX_PAGES: Final = 20
MAX_TITLE_LENGTH: Final = 200
MAX_MESSAGE_LENGTH: Final = 2000
MAX_BAR_TEXT_LENGTH: Final = 200
MAX_IDS_PER_WIDGET: Final = 100
NEXT_COUNT_MIN: Final = 1
NEXT_COUNT_MAX: Final = 10
LOTS_HORIZON_MIN: Final = 1
LOTS_HORIZON_MAX: Final = 60
DELIVERIES_HORIZON_MIN: Final = 0
DELIVERIES_HORIZON_MAX: Final = 30
EXTERNAL_WORK_HORIZON_MIN: Final = 0
EXTERNAL_WORK_HORIZON_MAX: Final = 30
WEATHER_DAYS_MIN: Final = 0
WEATHER_DAYS_MAX: Final = 7
MAX_PLACE_NAME_LENGTH: Final = 200
DETAIL_NEXT_COUNT_MIN: Final = 0
DETAIL_NEXT_COUNT_MAX: Final = 5
# Two decimals keep a place to about a kilometre, which is all a forecast
# needs and all the screen tells the weather service.
COORDINATE_DECIMALS: Final = 2


@dataclass(frozen=True)
class MachineBoardWidget:
    """Current and next orders of the chosen machines and pool members; no
    selection at all means every active machine."""

    title: str | None = None
    machine_ids: tuple[int, ...] = ()
    pool_ids: tuple[int, ...] = ()
    next_count: int = 3
    type: str = field(default=InfoscreenWidgetType.MACHINE_BOARD.value, init=False)


@dataclass(frozen=True)
class LotsDueWidget:
    """Open lots due within the horizon, optionally only those with orders
    on the chosen pools."""

    title: str | None = None
    horizon_days: int = 7
    pool_ids: tuple[int, ...] = ()
    show_customer: bool = False
    type: str = field(default=InfoscreenWidgetType.LOTS_DUE.value, init=False)


@dataclass(frozen=True)
class LateLotsWidget:
    title: str | None = None
    show_customer: bool = False
    type: str = field(default=InfoscreenWidgetType.LATE_LOTS.value, init=False)


@dataclass(frozen=True)
class QaQueueWidget:
    title: str | None = None
    type: str = field(default=InfoscreenWidgetType.QA_QUEUE.value, init=False)


@dataclass(frozen=True)
class DeliveriesExpectedWidget:
    """Supplier deliveries expected from today to `horizon_days` ahead."""

    title: str | None = None
    horizon_days: int = 0
    # Adds the open lines expected before today, ahead of today's.
    show_overdue: bool = False
    type: str = field(default=InfoscreenWidgetType.DELIVERIES_EXPECTED.value, init=False)


@dataclass(frozen=True)
class ExternalWorkWidget:
    """The parts that go to a supplier for an outside process and must leave
    from today to `horizon_days` ahead, by their latest pickup."""

    title: str | None = None
    horizon_days: int = 7
    # Adds the parts whose latest pickup has passed, ahead of today's.
    show_overdue: bool = True
    # Only these methods; none means every method.
    fabrication_method_ids: tuple[int, ...] = ()
    # Only parts already on a supplier's order.
    only_with_supplier: bool = False
    layout: str = InfoscreenExternalWorkLayout.DAYS.value
    type: str = field(default=InfoscreenWidgetType.EXTERNAL_WORK.value, init=False)


@dataclass(frozen=True)
class MessageWidget:
    title: str | None = None
    text: str = ""
    severity: str = InfoscreenMessageSeverity.INFO.value
    text_align: str = InfoscreenTextAlign.LEFT.value
    vertical_align: str = InfoscreenVerticalAlign.MIDDLE.value
    type: str = field(default=InfoscreenWidgetType.MESSAGE.value, init=False)


@dataclass(frozen=True)
class ClockWidget:
    title: str | None = None
    show_date: bool = True
    show_next_holiday: bool = False
    show_seconds: bool = False
    style: str = InfoscreenClockStyle.DIGITAL.value
    type: str = field(default=InfoscreenWidgetType.CLOCK.value, init=False)


@dataclass(frozen=True)
class WeatherWidget:
    """The forecast for a place, a town picked by name and never a site.
    The coordinates are the town centre's, rounded to two decimals."""

    location_name: str
    country_code: str
    latitude: float
    longitude: float
    title: str | None = None
    region: str | None = None
    days: int = 3
    show_wind: bool = False
    type: str = field(default=InfoscreenWidgetType.WEATHER.value, init=False)


@dataclass(frozen=True)
class ProductsWidget:
    """The active products, optionally with their active projects."""

    title: str | None = None
    show_projects: bool = False
    show_customer: bool = False
    type: str = field(default=InfoscreenWidgetType.PRODUCTS.value, init=False)


@dataclass(frozen=True)
class ProjectsWidget:
    """The active projects."""

    title: str | None = None
    show_customer: bool = False
    type: str = field(default=InfoscreenWidgetType.PROJECTS.value, init=False)


@dataclass(frozen=True)
class MachineDetailWidget:
    """Everything about the work on one machine: the order running on it, or
    the next one, with its item, drawing, raw material and lot."""

    machine_id: int
    title: str | None = None
    next_count: int = 3
    show_drawing: bool = True
    show_customer: bool = False
    type: str = field(default=InfoscreenWidgetType.MACHINE_DETAIL.value, init=False)


InfoscreenWidget = (
    MachineBoardWidget
    | LotsDueWidget
    | LateLotsWidget
    | QaQueueWidget
    | DeliveriesExpectedWidget
    | MessageWidget
    | ClockWidget
    | WeatherWidget
    | ProductsWidget
    | ProjectsWidget
    | MachineDetailWidget
    | ExternalWorkWidget
)


@dataclass(frozen=True)
class InfoscreenBar:
    """A header or footer bar with three areas, each listing its items left
    to right. An item appears at most once across the whole bar. `text` is
    what the `text` item shows. The center area is centred on the screen
    whatever the widths of the other two."""

    left: tuple[str, ...] = ()
    center: tuple[str, ...] = ()
    right: tuple[str, ...] = ()
    text: str | None = None

    @property
    def items(self) -> tuple[str, ...]:
        return self.left + self.center + self.right

    @property
    def shows_next_holiday(self) -> bool:
        return InfoscreenBarItem.NEXT_HOLIDAY.value in self.items


BAR_AREAS: Final = ("left", "center", "right")

DEFAULT_HEADER: Final = InfoscreenBar(
    left=(InfoscreenBarItem.LOGO.value, InfoscreenBarItem.TITLE.value),
    right=(InfoscreenBarItem.CLOCK.value,),
)
DEFAULT_FOOTER: Final = InfoscreenBar(right=(InfoscreenBarItem.LAST_UPDATED.value,))


@dataclass(frozen=True)
class InfoscreenPage:
    layout: str
    slots: tuple[InfoscreenWidget | None, ...]


def _fail(where: str, message: str) -> InvalidInfoscreenConfigError:
    return InvalidInfoscreenConfigError(f"{where}: {message}")


def _title(raw: Mapping[str, Any], where: str) -> str | None:
    value = raw.get("title")
    if value is None:
        return None
    if not isinstance(value, str):
        raise _fail(where, "title must be text.")
    value = value.strip()
    if len(value) > MAX_TITLE_LENGTH:
        raise _fail(where, f"title must be at most {MAX_TITLE_LENGTH} characters.")
    return value or None


def _bool(raw: Mapping[str, Any], key: str, default: bool, where: str) -> bool:
    value = raw.get(key, default)
    if not isinstance(value, bool):
        raise _fail(where, f"{key} must be true or false.")
    return value


def _int(
    raw: Mapping[str, Any], key: str, default: int, bounds: tuple[int, int], where: str
) -> int:
    value = raw.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise _fail(where, f"{key} must be a whole number.")
    low, high = bounds
    if not low <= value <= high:
        raise _fail(where, f"{key} must be between {low} and {high}.")
    return value


def _ids(raw: Mapping[str, Any], key: str, where: str) -> tuple[int, ...]:
    value = raw.get(key, [])
    if not isinstance(value, list | tuple):
        raise _fail(where, f"{key} must be a list of ids.")
    ids: list[int] = []
    for entry in value:
        if isinstance(entry, bool) or not isinstance(entry, int) or entry <= 0:
            raise _fail(where, f"{key} must hold positive ids only.")
        if entry not in ids:
            ids.append(entry)
    if len(ids) > MAX_IDS_PER_WIDGET:
        raise _fail(where, f"{key} may hold at most {MAX_IDS_PER_WIDGET} ids.")
    return tuple(ids)


def _float(raw: Mapping[str, Any], key: str, bounds: tuple[float, float], where: str) -> float:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise _fail(where, f"{key} must be a number.")
    low, high = bounds
    if not low <= value <= high:
        raise _fail(where, f"{key} must be between {low} and {high}.")
    return round(float(value), COORDINATE_DECIMALS)


def _text(raw: Mapping[str, Any], key: str, where: str, *, required: bool) -> str | None:
    value = raw.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise _fail(where, f"{key} is required.")
        return None
    if not isinstance(value, str):
        raise _fail(where, f"{key} must be text.")
    value = value.strip()
    if len(value) > MAX_PLACE_NAME_LENGTH:
        raise _fail(where, f"{key} must be at most {MAX_PLACE_NAME_LENGTH} characters.")
    return value


def _country_code(raw: Mapping[str, Any], where: str) -> str:
    value = raw.get("country_code")
    if not isinstance(value, str) or len(value) != 2 or not value.isascii() or not value.isalpha():
        raise _fail(where, "country_code must be a two letter country code.")
    return value.upper()


def _id(raw: Mapping[str, Any], key: str, where: str) -> int:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise _fail(where, f"{key} must be a positive id.")
    return value


def _choice(raw: Mapping[str, Any], key: str, allowed: list[str], default: str, where: str) -> str:
    value = raw.get(key, default)
    if value not in allowed:
        raise _fail(where, f"{key} must be one of {allowed}.")
    return str(value)


def parse_widget(raw: Mapping[str, Any], where: str = "widget") -> InfoscreenWidget:
    """One widget config from plain data, validated against the rules of its
    type. Raises InvalidInfoscreenConfigError naming `where`."""
    widget_type = raw.get("type")
    title = _title(raw, where)
    if widget_type == InfoscreenWidgetType.MACHINE_BOARD.value:
        return MachineBoardWidget(
            title=title,
            machine_ids=_ids(raw, "machine_ids", where),
            pool_ids=_ids(raw, "pool_ids", where),
            next_count=_int(raw, "next_count", 3, (NEXT_COUNT_MIN, NEXT_COUNT_MAX), where),
        )
    if widget_type == InfoscreenWidgetType.LOTS_DUE.value:
        return LotsDueWidget(
            title=title,
            horizon_days=_int(raw, "horizon_days", 7, (LOTS_HORIZON_MIN, LOTS_HORIZON_MAX), where),
            pool_ids=_ids(raw, "pool_ids", where),
            show_customer=_bool(raw, "show_customer", False, where),
        )
    if widget_type == InfoscreenWidgetType.LATE_LOTS.value:
        return LateLotsWidget(title=title, show_customer=_bool(raw, "show_customer", False, where))
    if widget_type == InfoscreenWidgetType.QA_QUEUE.value:
        return QaQueueWidget(title=title)
    if widget_type == InfoscreenWidgetType.DELIVERIES_EXPECTED.value:
        return DeliveriesExpectedWidget(
            title=title,
            horizon_days=_int(
                raw,
                "horizon_days",
                0,
                (DELIVERIES_HORIZON_MIN, DELIVERIES_HORIZON_MAX),
                where,
            ),
            show_overdue=_bool(raw, "show_overdue", False, where),
        )
    if widget_type == InfoscreenWidgetType.EXTERNAL_WORK.value:
        return ExternalWorkWidget(
            title=title,
            horizon_days=_int(
                raw,
                "horizon_days",
                7,
                (EXTERNAL_WORK_HORIZON_MIN, EXTERNAL_WORK_HORIZON_MAX),
                where,
            ),
            show_overdue=_bool(raw, "show_overdue", True, where),
            fabrication_method_ids=_ids(raw, "fabrication_method_ids", where),
            only_with_supplier=_bool(raw, "only_with_supplier", False, where),
            layout=_choice(
                raw,
                "layout",
                InfoscreenExternalWorkLayout.values(),
                InfoscreenExternalWorkLayout.DAYS.value,
                where,
            ),
        )
    if widget_type == InfoscreenWidgetType.MESSAGE.value:
        text = raw.get("text", "")
        if not isinstance(text, str) or not text.strip():
            raise _fail(where, "a message needs a text.")
        if len(text) > MAX_MESSAGE_LENGTH:
            raise _fail(where, f"text must be at most {MAX_MESSAGE_LENGTH} characters.")
        return MessageWidget(
            title=title,
            text=text,
            severity=_choice(
                raw,
                "severity",
                InfoscreenMessageSeverity.values(),
                InfoscreenMessageSeverity.INFO.value,
                where,
            ),
            text_align=_choice(
                raw,
                "text_align",
                InfoscreenTextAlign.values(),
                InfoscreenTextAlign.LEFT.value,
                where,
            ),
            vertical_align=_choice(
                raw,
                "vertical_align",
                InfoscreenVerticalAlign.values(),
                InfoscreenVerticalAlign.MIDDLE.value,
                where,
            ),
        )
    if widget_type == InfoscreenWidgetType.CLOCK.value:
        return ClockWidget(
            title=title,
            show_date=_bool(raw, "show_date", True, where),
            show_next_holiday=_bool(raw, "show_next_holiday", False, where),
            show_seconds=_bool(raw, "show_seconds", False, where),
            style=_choice(
                raw,
                "style",
                InfoscreenClockStyle.values(),
                InfoscreenClockStyle.DIGITAL.value,
                where,
            ),
        )
    if widget_type == InfoscreenWidgetType.WEATHER.value:
        return WeatherWidget(
            title=title,
            location_name=cast(str, _text(raw, "location_name", where, required=True)),
            region=_text(raw, "region", where, required=False),
            country_code=_country_code(raw, where),
            latitude=_float(raw, "latitude", (-90.0, 90.0), where),
            longitude=_float(raw, "longitude", (-180.0, 180.0), where),
            days=_int(raw, "days", 3, (WEATHER_DAYS_MIN, WEATHER_DAYS_MAX), where),
            show_wind=_bool(raw, "show_wind", False, where),
        )
    if widget_type == InfoscreenWidgetType.PRODUCTS.value:
        return ProductsWidget(
            title=title,
            show_projects=_bool(raw, "show_projects", False, where),
            show_customer=_bool(raw, "show_customer", False, where),
        )
    if widget_type == InfoscreenWidgetType.PROJECTS.value:
        return ProjectsWidget(title=title, show_customer=_bool(raw, "show_customer", False, where))
    if widget_type == InfoscreenWidgetType.MACHINE_DETAIL.value:
        return MachineDetailWidget(
            title=title,
            machine_id=_id(raw, "machine_id", where),
            next_count=_int(
                raw, "next_count", 3, (DETAIL_NEXT_COUNT_MIN, DETAIL_NEXT_COUNT_MAX), where
            ),
            show_drawing=_bool(raw, "show_drawing", True, where),
            show_customer=_bool(raw, "show_customer", False, where),
        )
    raise _fail(where, f"unknown widget type {widget_type!r}.")


def parse_pages(raw_pages: Sequence[Mapping[str, Any]]) -> list[InfoscreenPage]:
    """Every page from plain data. Each page needs a known layout and exactly
    one slot per layout position."""
    if len(raw_pages) > MAX_PAGES:
        raise InvalidInfoscreenConfigError(f"A screen may have at most {MAX_PAGES} pages.")
    pages: list[InfoscreenPage] = []
    for page_index, raw_page in enumerate(raw_pages, start=1):
        where = f"Page {page_index}"
        layout = raw_page.get("layout")
        if layout not in SLOTS_PER_LAYOUT:
            raise _fail(where, f"layout must be one of {list(SLOTS_PER_LAYOUT)}.")
        raw_slots = raw_page.get("slots")
        if not isinstance(raw_slots, list | tuple):
            raise _fail(where, "slots must be a list.")
        expected = SLOTS_PER_LAYOUT[layout]
        if len(raw_slots) != expected:
            raise _fail(where, f"the {layout} layout has {expected} slot(s), not {len(raw_slots)}.")
        slots: list[InfoscreenWidget | None] = []
        for slot_index, raw_slot in enumerate(raw_slots, start=1):
            if raw_slot is None:
                slots.append(None)
                continue
            if not isinstance(raw_slot, Mapping):
                raise _fail(f"{where}, slot {slot_index}", "a slot holds a widget or nothing.")
            slots.append(parse_widget(raw_slot, f"{where}, slot {slot_index}"))
        pages.append(InfoscreenPage(layout=str(layout), slots=tuple(slots)))
    return pages


def parse_bar(raw: Mapping[str, Any], where: str = "bar") -> InfoscreenBar:
    """A header or footer bar from plain data. Every item must be known and
    appear once across the three areas; the text is trimmed and may be
    empty."""
    allowed = InfoscreenBarItem.values()
    seen: list[str] = []
    areas: dict[str, tuple[str, ...]] = {}
    for area in BAR_AREAS:
        raw_items = raw.get(area, [])
        if not isinstance(raw_items, list | tuple):
            raise _fail(where, f"{area} must be a list.")
        for item in raw_items:
            if item not in allowed:
                raise _fail(where, f"items must be among {allowed}, not {item!r}.")
            if item in seen:
                raise _fail(where, f"{item!r} appears more than once.")
            seen.append(str(item))
        areas[area] = tuple(str(item) for item in raw_items)
    text = raw.get("text")
    if text is not None:
        if not isinstance(text, str):
            raise _fail(where, "text must be text.")
        if len(text) > MAX_BAR_TEXT_LENGTH:
            raise _fail(where, f"text must be at most {MAX_BAR_TEXT_LENGTH} characters.")
        text = text.strip() or None
    return InfoscreenBar(
        left=areas["left"], center=areas["center"], right=areas["right"], text=text
    )


def bar_to_data(bar: InfoscreenBar) -> dict[str, Any]:
    """Plain data of a bar, the shape parse_bar reads."""
    return {
        "left": list(bar.left),
        "center": list(bar.center),
        "right": list(bar.right),
        "text": bar.text,
    }


def widget_to_data(widget: InfoscreenWidget) -> dict[str, Any]:
    """Plain data of one widget config, tuples as lists."""
    data: dict[str, Any] = {"type": widget.type}
    for name, value in vars(widget).items():
        if name == "type":
            continue
        data[name] = list(value) if isinstance(value, tuple) else value
    return data


def pages_to_data(pages: Sequence[InfoscreenPage]) -> list[dict[str, Any]]:
    """Plain data of every page, the shape parse_pages reads."""
    return [
        {
            "layout": page.layout,
            "slots": [widget_to_data(slot) if slot is not None else None for slot in page.slots],
        }
        for page in pages
    ]
