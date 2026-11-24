"""
The infoscreen feed: one screen's settings plus ready-made data for each of
its widgets, built for wall displays nobody signs in to.

These models are written for the feed alone and carry no person at all, no
name, username, email, user id, creator, operator or orderer, because a
display hangs where anyone can read it. A customer name, a company and not a
person but possibly confidential, appears only when the widget asks for it.
tests/integration/test_infoscreen_feed_gdpr.py walks the published schema of
the feed and fails on any such field. A row's `thumbnail_url` is a signed
link to the item's thumbnail that needs no credential and expires within
90 minutes.
"""

from datetime import date
from datetime import datetime
from typing import Annotated
from typing import Literal

from pydantic import Field

from src.modules.operations.application.dto.infoscreen_dto import ColorMode
from src.modules.operations.application.dto.infoscreen_dto import InfoscreenBar
from src.modules.operations.application.dto.infoscreen_dto import InfoscreenPage
from src.modules.operations.application.dto.infoscreen_dto import MessageSeverity
from src.modules.operations.application.dto.infoscreen_dto import TextAlign
from src.modules.operations.application.dto.infoscreen_dto import ThemePreset
from src.modules.operations.application.dto.infoscreen_dto import VerticalAlign
from src.modules.operations.application.dto.terminal_dto import TerminalBroadcastMessage
from src.modules.platform.application.dto.base import ResultModel
from src.modules.platform.domain.value_objects.language import Language

MachineState = Literal["running", "idle", "down", "closed"]


class InfoscreenFeedScreen(ResultModel):
    id: int
    name: str
    color_mode: ColorMode
    theme_preset: ThemePreset | None
    primary_color: str | None
    rotation_seconds: int
    show_header: bool
    header: InfoscreenBar
    show_footer: bool
    footer: InfoscreenBar
    pages: list[InfoscreenPage]


class InfoscreenFeedBanner(ResultModel):
    text: str
    severity: str


class InfoscreenOrderCard(ResultModel):
    production_order_id: int
    lot_number: str | None
    part_number: str | None
    item_name: str | None
    project_number: str | None
    quantity: float | None
    status: str
    thumbnail_url: str | None


class MachineBoardMachine(ResultModel):
    machine_id: int
    machine_name: str
    state: MachineState
    downtime_reason: str | None
    current: InfoscreenOrderCard | None
    next: list[InfoscreenOrderCard]


class MachineBoardPool(ResultModel):
    """Orders queued on a pool that no machine has taken yet, in queue
    order; `waiting_total` counts them all, `waiting` shows the first few."""

    pool_id: int
    pool_name: str
    waiting: list[InfoscreenOrderCard]
    waiting_total: int


class MachineBoardWidgetData(ResultModel):
    type: Literal["machine_board"] = "machine_board"
    machines: list[MachineBoardMachine]
    pools: list[MachineBoardPool]


class InfoscreenLotRow(ResultModel):
    lot_id: int
    lot_number: str
    part_number: str | None
    item_name: str | None
    project_number: str | None
    customer_name: str | None
    target_date: date | None
    status: str
    days_late: int | None
    thumbnail_url: str | None


class LotsDueWidgetData(ResultModel):
    type: Literal["lots_due"] = "lots_due"
    lots: list[InfoscreenLotRow]


class LateLotsWidgetData(ResultModel):
    type: Literal["late_lots"] = "late_lots"
    lots: list[InfoscreenLotRow]


class InfoscreenQaRow(ResultModel):
    task_id: int
    lot_number: str | None
    part_number: str | None
    item_name: str | None
    status: str
    since: datetime | None
    thumbnail_url: str | None


class QaQueueWidgetData(ResultModel):
    type: Literal["qa_queue"] = "qa_queue"
    tasks: list[InfoscreenQaRow]


class InfoscreenDeliveryRow(ResultModel):
    order_number: str | None
    part_number: str | None
    item_name: str | None
    quantity: float | None
    unit: str | None
    supplier_name: str | None
    expected_date: date | None
    # Days past the expected date for an overdue line, None otherwise.
    days_late: int | None = None
    thumbnail_url: str | None


class DeliveriesExpectedWidgetData(ResultModel):
    type: Literal["deliveries_expected"] = "deliveries_expected"
    deliveries: list[InfoscreenDeliveryRow]


class InfoscreenExternalWorkRow(ResultModel):
    """A part that goes to a supplier for an outside process. No persons
    and no customer: the lot, the item, the methods and a company."""

    lot_number: str
    part_number: str | None
    item_name: str | None
    quantity: float
    # The methods' names in the screen's language.
    methods: list[str]
    supplier_name: str | None
    # The supplier is the methods' default, the part is not ordered yet.
    supplier_suggested: bool
    latest_pickup_date: date | None
    # When the pieces can go out, None once they are there.
    ready_from: date | None
    ready_now: bool
    # The day it is due back from the supplier.
    due_back_date: date | None
    # Why the part needs attention, the procurement list's alert.
    alert: Literal["not_ready_in_time", "overdue"] | None
    days_late: int | None = None
    thumbnail_url: str | None


class ExternalWorkWidgetData(ResultModel):
    type: Literal["external_work"] = "external_work"
    rows: list[InfoscreenExternalWorkRow]


class MessageWidgetData(ResultModel):
    type: Literal["message"] = "message"
    # Markdown, rendered on the display.
    text: str
    severity: MessageSeverity
    text_align: TextAlign
    vertical_align: VerticalAlign


class InfoscreenHoliday(ResultModel):
    date: date
    name: str


class ClockWidgetData(ResultModel):
    type: Literal["clock"] = "clock"
    next_holiday: InfoscreenHoliday | None


class InfoscreenWeatherNow(ResultModel):
    temperature: float | None
    # The weather service's symbol for the coming hour, such as
    # `partlycloudy_day`, which the display draws as an icon.
    symbol: str | None
    wind_speed: float | None
    is_day: bool


class InfoscreenWeatherDay(ResultModel):
    date: date
    symbol: str | None
    temperature_max: float | None
    temperature_min: float | None
    precipitation_mm: float | None


class WeatherWidgetData(ResultModel):
    """The weather at the widget's town. `status` is `ok` with a forecast,
    `unavailable` when the service failed and nothing stands in, and `off`
    when an admin switched the weather off. `fetched_at` tells how old the
    forecast is; it lies in the past when an earlier one stands in.
    `attribution` names the source the display credits. Temperatures are in
    degrees Celsius, the wind in km/h and precipitation in millimetres."""

    type: Literal["weather"] = "weather"
    status: Literal["ok", "unavailable", "off"]
    location_name: str
    region: str | None
    now: InfoscreenWeatherNow | None
    days: list[InfoscreenWeatherDay]
    fetched_at: datetime | None
    attribution: str | None


class InfoscreenProjectRef(ResultModel):
    project_id: int
    project_number: str
    description: str | None


class InfoscreenProductRow(ResultModel):
    product_id: int
    product_number: str
    designation: str | None
    description: str | None
    machine_type: str | None
    customer_name: str | None
    projects: list[InfoscreenProjectRef]


class ProductsWidgetData(ResultModel):
    type: Literal["products"] = "products"
    products: list[InfoscreenProductRow]


class InfoscreenProjectRow(ResultModel):
    project_id: int
    project_number: str
    description: str | None
    product_number: str | None
    product_designation: str | None
    customer_name: str | None


class ProjectsWidgetData(ResultModel):
    type: Literal["projects"] = "projects"
    projects: list[InfoscreenProjectRow]


class InfoscreenRawMaterial(ResultModel):
    """The input the made item is made from: a source item (raw stock) or a
    bought item, with how far the lot's input demand has come."""

    kind: Literal["source", "bought"]
    part_number: str | None
    name: str | None
    material: str | None
    dimension: str | None
    demand_status: str | None
    expected_delivery: date | None


class InfoscreenMachineLot(ResultModel):
    lot_id: int
    lot_number: str
    status: str
    quantity: float
    project_number: str | None
    customer_name: str | None


class InfoscreenMachineOrder(ResultModel):
    """The order the machine detail widget shows, with no times: the made
    item with its large picture and drawing, its metadata, raw material and
    the lot the order belongs to."""

    production_order_id: int
    # On the machine now (running or paused) rather than next in line.
    current: bool
    status: str
    lot_number: str | None
    part_number: str | None
    item_name: str | None
    revision: str | None
    material: str | None
    mass_grams: int | None
    base_size: str | None
    quantity: float
    quantity_completed: float
    step_sequence: int | None
    step_count: int | None
    picture_url: str | None
    drawing_url: str | None
    raw_material: InfoscreenRawMaterial | None
    lot: InfoscreenMachineLot | None


class MachineDetailWidgetData(ResultModel):
    """One machine; `machine_name` is None when the machine was archived or
    removed since the screen was set up."""

    type: Literal["machine_detail"] = "machine_detail"
    machine_id: int
    machine_name: str | None
    state: MachineState | None
    downtime_reason: str | None
    order: InfoscreenMachineOrder | None
    next: list[InfoscreenOrderCard]


InfoscreenWidgetData = Annotated[
    MachineBoardWidgetData
    | LotsDueWidgetData
    | LateLotsWidgetData
    | QaQueueWidgetData
    | DeliveriesExpectedWidgetData
    | MessageWidgetData
    | ClockWidgetData
    | WeatherWidgetData
    | ProductsWidgetData
    | ProjectsWidgetData
    | MachineDetailWidgetData
    | ExternalWorkWidgetData,
    Field(discriminator="type"),
]


class InfoscreenFeedResult(ResultModel):
    """`widgets[p][s]` is the data for `infoscreen.pages[p].slots[s]`, None
    for an empty slot. `next_holiday` is filled when a shown bar has the
    next_holiday item. `timezone` is the tenant's default timezone (an IANA
    name), the one the display draws every time and date in. `language` is
    the screen's language, or the tenant's default language when the screen
    has none. `broadcast` is the newest active message to terminals that
    reaches the reader: the device's own for a device, and for the preview
    one that goes to every terminal or picks this screen."""

    infoscreen: InfoscreenFeedScreen
    widgets: list[list[InfoscreenWidgetData | None]]
    banner: InfoscreenFeedBanner | None
    next_holiday: InfoscreenHoliday | None
    generated_at: datetime
    backend_version: str
    timezone: str
    language: Language
    broadcast: TerminalBroadcastMessage | None = None
