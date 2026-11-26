"""
Builds the feed of one infoscreen: its settings plus ready-made data for
every widget slot, the global banner when the screen shows it, and the
next tenant holiday when a shown header or footer has that item, and the
language the screen shows its built-in copy in. Rows that
name an item carry a signed link to its thumbnail (infoscreen_thumbnails),
looked up in one query per widget and item kind. The
device feed and the builder preview both call this, so a display shows
exactly what the preview showed.

Every row is mapped into the feed's own models, which carry no person
(see infoscreen_feed_dto.py), and a customer name only when the widget asks
for it. The sources are the ones the app's own pages read: the machines'
live orders with their stored planned window, open downtimes and the
machine calendars; the lots table's target date; the late lots KPI's
candidates; the open inspection orders of the QA worklist; ordered supplier
lines by expected delivery date; the active products and projects; the made
item, its drawing and raw material and the lot behind a machine's order;
and the tenant holidays. Reading the data needs no permission, as it does
not on those pages. The weather comes from the weather service, unless an
admin switched it off.
"""

from dataclasses import dataclass
from datetime import date
from datetime import datetime
from datetime import timedelta
from typing import Literal
from typing import cast

from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.value_objects.item_kind import ItemKind
from src.modules.catalogue.domain.value_objects.made_item_file_category import MadeItemFileCategory
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.catalogue.ports.outbound.catalogue_queries import IItemPictureQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import IMadeItemFileQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import IMadeItemQueries
from src.modules.fulfillment.application.facade.external_work import ExternalWorkAlert
from src.modules.fulfillment.application.facade.external_work import ExternalWorkQuery
from src.modules.fulfillment.application.facade.external_work import ExternalWorkStage
from src.modules.fulfillment.application.facade.external_work import GetExternalWork
from src.modules.fulfillment.application.facade.scheduling import IMachineCalendarRepository
from src.modules.fulfillment.application.facade.scheduling import IMachinePoolRepository
from src.modules.fulfillment.application.facade.scheduling import IProductionMachineRepository
from src.modules.fulfillment.application.facade.scheduling import SchedulingRepos
from src.modules.fulfillment.application.facade.scheduling import build_machine_calendars
from src.modules.fulfillment.application.facade.scheduling import describe_lot_target_dates
from src.modules.fulfillment.domain.entities.machine_pool import MachinePool
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.value_objects.lot_status import TERMINAL_LOT_STATUSES
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.ports.outbound.fulfillment_queries import IMachineDowntimeQueries
from src.modules.fulfillment.ports.outbound.fulfillment_queries import IOrderItemQueries
from src.modules.fulfillment.ports.outbound.fulfillment_queries import IOrderQueries
from src.modules.fulfillment.ports.outbound.fulfillment_queries import LotFilterDto
from src.modules.fulfillment.ports.outbound.fulfillment_queries import OrderFilterDto
from src.modules.fulfillment.ports.outbound.fulfillment_queries import ProductionOrderFilterDto
from src.modules.operations.application.dto.infoscreen_dto import ColorMode
from src.modules.operations.application.dto.infoscreen_dto import MessageSeverity
from src.modules.operations.application.dto.infoscreen_dto import TextAlign
from src.modules.operations.application.dto.infoscreen_dto import ThemePreset
from src.modules.operations.application.dto.infoscreen_dto import VerticalAlign
from src.modules.operations.application.dto.infoscreen_feed_dto import ClockWidgetData
from src.modules.operations.application.dto.infoscreen_feed_dto import DeliveriesExpectedWidgetData
from src.modules.operations.application.dto.infoscreen_feed_dto import ExternalWorkWidgetData
from src.modules.operations.application.dto.infoscreen_feed_dto import InfoscreenDeliveryRow
from src.modules.operations.application.dto.infoscreen_feed_dto import InfoscreenExternalWorkRow
from src.modules.operations.application.dto.infoscreen_feed_dto import InfoscreenFeedBanner
from src.modules.operations.application.dto.infoscreen_feed_dto import InfoscreenFeedResult
from src.modules.operations.application.dto.infoscreen_feed_dto import InfoscreenFeedScreen
from src.modules.operations.application.dto.infoscreen_feed_dto import InfoscreenHoliday
from src.modules.operations.application.dto.infoscreen_feed_dto import InfoscreenLotRow
from src.modules.operations.application.dto.infoscreen_feed_dto import InfoscreenMachineLot
from src.modules.operations.application.dto.infoscreen_feed_dto import InfoscreenMachineOrder
from src.modules.operations.application.dto.infoscreen_feed_dto import InfoscreenOrderCard
from src.modules.operations.application.dto.infoscreen_feed_dto import InfoscreenProductRow
from src.modules.operations.application.dto.infoscreen_feed_dto import InfoscreenProjectRef
from src.modules.operations.application.dto.infoscreen_feed_dto import InfoscreenProjectRow
from src.modules.operations.application.dto.infoscreen_feed_dto import InfoscreenQaRow
from src.modules.operations.application.dto.infoscreen_feed_dto import InfoscreenRawMaterial
from src.modules.operations.application.dto.infoscreen_feed_dto import InfoscreenWeatherDay
from src.modules.operations.application.dto.infoscreen_feed_dto import InfoscreenWeatherNow
from src.modules.operations.application.dto.infoscreen_feed_dto import InfoscreenWidgetData
from src.modules.operations.application.dto.infoscreen_feed_dto import LateLotsWidgetData
from src.modules.operations.application.dto.infoscreen_feed_dto import LotsDueWidgetData
from src.modules.operations.application.dto.infoscreen_feed_dto import MachineBoardMachine
from src.modules.operations.application.dto.infoscreen_feed_dto import MachineBoardPool
from src.modules.operations.application.dto.infoscreen_feed_dto import MachineBoardWidgetData
from src.modules.operations.application.dto.infoscreen_feed_dto import MachineDetailWidgetData
from src.modules.operations.application.dto.infoscreen_feed_dto import MessageWidgetData
from src.modules.operations.application.dto.infoscreen_feed_dto import ProductsWidgetData
from src.modules.operations.application.dto.infoscreen_feed_dto import ProjectsWidgetData
from src.modules.operations.application.dto.infoscreen_feed_dto import QaQueueWidgetData
from src.modules.operations.application.dto.infoscreen_feed_dto import WeatherWidgetData
from src.modules.operations.application.facade.infoscreen_thumbnails import ThumbnailLinker
from src.modules.operations.application.mappers.infoscreen_mapper import bar_to_dto
from src.modules.operations.application.mappers.infoscreen_mapper import pages_to_dto
from src.modules.operations.domain.entities.infoscreen import Infoscreen
from src.modules.operations.domain.errors import WeatherUnavailableError
from src.modules.operations.domain.value_objects.infoscreen import ClockWidget
from src.modules.operations.domain.value_objects.infoscreen import DeliveriesExpectedWidget
from src.modules.operations.domain.value_objects.infoscreen import ExternalWorkWidget
from src.modules.operations.domain.value_objects.infoscreen import InfoscreenWidget
from src.modules.operations.domain.value_objects.infoscreen import LateLotsWidget
from src.modules.operations.domain.value_objects.infoscreen import LotsDueWidget
from src.modules.operations.domain.value_objects.infoscreen import MachineBoardWidget
from src.modules.operations.domain.value_objects.infoscreen import MachineDetailWidget
from src.modules.operations.domain.value_objects.infoscreen import MessageWidget
from src.modules.operations.domain.value_objects.infoscreen import ProductsWidget
from src.modules.operations.domain.value_objects.infoscreen import ProjectsWidget
from src.modules.operations.domain.value_objects.infoscreen import QaQueueWidget
from src.modules.operations.domain.value_objects.infoscreen import WeatherWidget
from src.modules.operations.ports.outbound.operations_settings_repository import (
    IOperationsSettingsRepository,
)
from src.modules.operations.ports.outbound.weather_port import IWeatherService
from src.modules.operations.ports.outbound.weather_port import WeatherClientContact
from src.modules.platform.application.services.tenant_timezone import tenant_zone
from src.modules.platform.const import VERSION
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.quality.domain.policies.production_kpi import is_lot_late
from src.modules.quality.ports.outbound.quality_queries import IProductionKpiQueries
from src.modules.quality.ports.outbound.quality_queries import KpiScope
from src.modules.workspace.domain.entities.project import Project
from src.modules.workspace.domain.value_objects.project_status import ProjectStatus
from src.modules.workspace.ports.outbound.workspace_queries import IProductQueries
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries
from src.modules.workspace.ports.outbound.workspace_queries import ProjectFilterDto
from src.read.domain.services import infoscreen_feed_rules as rules
from src.shared_kernel.domain.services.clock import now_utc

# Row caps per widget; a wall display cannot show more anyway.
_MAX_LOT_ROWS = 50
# Lots read before sorting by target date, which the list query cannot
# order by.
_MAX_DUE_LOTS_READ = 500
_MAX_QA_ROWS = 50
_MAX_DELIVERY_ROWS = 50
# A screen shows a few dozen rows at most.
_MAX_EXTERNAL_WORK_ROWS = 60
# The stages of parts still in the house; handed over ones have left.
_EXTERNAL_WORK_NOT_SENT = (
    ExternalWorkStage.UNASSIGNED,
    ExternalWorkStage.PENDING,
    ExternalWorkStage.REQUESTED,
    ExternalWorkStage.ORDERED,
)
_EXTERNAL_WORK_ALERTS = (ExternalWorkAlert.NOT_READY_IN_TIME, ExternalWorkAlert.OVERDUE)
_MAX_DELIVERY_ORDERS = 200
_MAX_PRODUCTS = 100
_MAX_PROJECTS = 200

_OPEN_LOT_STATUSES = [s for s in LotStatus.values() if s not in TERMINAL_LOT_STATUSES]
_OPEN_QA_STATUSES = [
    ProductionOrderStatus.QUEUED.value,
    ProductionOrderStatus.IN_PROGRESS.value,
    ProductionOrderStatus.PAUSED.value,
]
_ORDERED_STATUSES = [
    OrderStatus.PARTIALLY_ORDERED.value,
    OrderStatus.ORDERED.value,
    OrderStatus.PARTIALLY_DELIVERED.value,
]
_ORDERED_ITEM_STATUSES = frozenset(
    {OrderItemStatus.ORDERED.value, OrderItemStatus.PARTIALLY_DELIVERED.value}
)


@dataclass(frozen=True)
class _FeedContext:
    """What every widget of one feed shares: the moment it is built, the
    tenant's today, and the thumbnail links."""

    now: datetime
    today: date
    links: ThumbnailLinker
    # The screen's language and the tenant's, for names kept per language.
    language: str
    default_language: str
    # The tenant's timezone, in which the weather counts its days.
    timezone: str
    # How Glados names itself to the weather service.
    weather_contact: WeatherClientContact


def _order_card(order: ProductionOrder, links: ThumbnailLinker) -> InfoscreenOrderCard:
    return InfoscreenOrderCard(
        production_order_id=order.id,
        lot_number=order.lot_number or None,
        part_number=order.made_item_part_number or None,
        item_name=order.made_item_article_name or None,
        project_number=order.project_number or None,
        quantity=order.quantity,
        status=order.status,
        thumbnail_url=links.url(ItemKind.MADE, order.made_item_id),
    )


def _lot_row(
    lot: ProductionLot,
    target: date | None,
    days_late: int | None,
    show_customer: bool,
    links: ThumbnailLinker,
) -> InfoscreenLotRow:
    return InfoscreenLotRow(
        lot_id=lot.id,
        lot_number=lot.lot_number,
        part_number=lot.made_item_part_number or None,
        item_name=lot.made_item_article_name or None,
        project_number=lot.project_number or None,
        customer_name=(lot.project_customer or None) if show_customer else None,
        target_date=target,
        status=lot.status,
        days_late=days_late,
        thumbnail_url=links.url(ItemKind.MADE, lot.made_item_id),
    )


def _line_item(item: OrderItem) -> tuple[ItemKind | None, int | None]:
    """The catalogue item a supplier line delivers, None for a virtual line."""
    if item.bought_item_id:
        return ItemKind.BOUGHT, item.bought_item_id
    if item.source_item_id:
        return ItemKind.SOURCE, item.source_item_id
    if item.made_item_id:
        return ItemKind.MADE, item.made_item_id
    return None, None


class BuildInfoscreenFeed:
    def __init__(
        self,
        repos: SchedulingRepos,
        machine_repo: IProductionMachineRepository,
        pool_repo: IMachinePoolRepository,
        downtime_repo: IMachineDowntimeQueries,
        calendar_repo: IMachineCalendarRepository,
        kpi_repo: IProductionKpiQueries,
        order_repo: IOrderQueries,
        order_item_repo: IOrderItemQueries,
        settings_repo: IOperationsSettingsRepository,
        picture_repo: IItemPictureQueries,
        product_repo: IProductQueries,
        project_repo: IProjectQueries,
        made_item_repo: IMadeItemQueries,
        made_item_file_repo: IMadeItemFileQueries,
        weather: IWeatherService,
        external_work: GetExternalWork,
    ) -> None:
        self._repos = repos
        self._machines = machine_repo
        self._pools = pool_repo
        self._downtimes = downtime_repo
        self._calendars = calendar_repo
        self._kpi = kpi_repo
        self._orders = order_repo
        self._order_items = order_item_repo
        self._settings = settings_repo
        self._pictures = picture_repo
        self._products = product_repo
        self._projects = project_repo
        self._made_items = made_item_repo
        self._made_item_files = made_item_file_repo
        self._weather = weather
        self._external_work_list = external_work

    async def execute(self, infoscreen: Infoscreen) -> InfoscreenFeedResult:
        now = now_utc()
        zone = await tenant_zone(self._settings)
        today = now.astimezone(zone).date()
        general = await self._settings.get_general()
        default_language = general.default_language
        language = infoscreen.language or default_language
        ctx = _FeedContext(
            now=now,
            today=today,
            links=ThumbnailLinker(self._pictures, now),
            language=language.value,
            default_language=default_language.value,
            timezone=str(zone),
            weather_contact=WeatherClientContact(
                email=general.contact_email or None,
                website=general.support_url or general.imprint_url or None,
            ),
        )
        widgets: list[list[InfoscreenWidgetData | None]] = [
            [await self._widget(slot, ctx) if slot is not None else None for slot in page.slots]
            for page in infoscreen.pages
        ]

        banner = None
        if infoscreen.show_banner:
            settings = await self._settings.get_banner()
            if rules.banner_visible(settings, now):
                banner = InfoscreenFeedBanner(text=settings.text, severity=settings.severity.value)

        return InfoscreenFeedResult(
            infoscreen=InfoscreenFeedScreen(
                id=infoscreen.id,
                name=infoscreen.name,
                color_mode=cast(ColorMode, infoscreen.color_mode),
                theme_preset=cast(ThemePreset | None, infoscreen.theme_preset),
                primary_color=infoscreen.primary_color,
                rotation_seconds=infoscreen.rotation_seconds,
                show_header=infoscreen.show_header,
                header=bar_to_dto(infoscreen.header),
                show_footer=infoscreen.show_footer,
                footer=bar_to_dto(infoscreen.footer),
                pages=pages_to_dto(infoscreen.pages),
            ),
            widgets=widgets,
            banner=banner,
            next_holiday=await self._bar_holiday(infoscreen, today),
            generated_at=now,
            backend_version=VERSION,
            # The resolved zone's IANA key, so an unknown setting arrives as
            # the UTC the backend itself falls back to.
            timezone=str(zone),
            language=language,
        )

    async def _widget(self, widget: InfoscreenWidget, ctx: _FeedContext) -> InfoscreenWidgetData:
        match widget:
            case MachineBoardWidget():
                return await self._machine_board(widget, ctx)
            case LotsDueWidget():
                return await self._lots_due(widget, ctx)
            case LateLotsWidget():
                return await self._late_lots(widget, ctx)
            case QaQueueWidget():
                return await self._qa_queue(ctx)
            case DeliveriesExpectedWidget():
                return await self._deliveries(widget, ctx)
            case MessageWidget():
                return MessageWidgetData(
                    text=widget.text,
                    severity=cast(MessageSeverity, widget.severity),
                    text_align=cast(TextAlign, widget.text_align),
                    vertical_align=cast(VerticalAlign, widget.vertical_align),
                )
            case ClockWidget():
                return await self._clock(widget, ctx.today)
            case WeatherWidget():
                return await self._weather_data(widget, ctx)
            case ProductsWidget():
                return await self._products_data(widget)
            case ProjectsWidget():
                return await self._projects_data(widget)
            case MachineDetailWidget():
                return await self._machine_detail(widget, ctx)
            case ExternalWorkWidget():
                return await self._external_work(widget, ctx)

    # ── Machine board ─────────────────────────────────────────────────

    async def _board_machines(self, widget: MachineBoardWidget) -> list[ProductionMachine]:
        """The chosen machines, then the members of the chosen pools, each
        once and archived ones left out. No selection means every active
        machine."""
        if not widget.machine_ids and not widget.pool_ids:
            return sorted(
                (m for m in await self._machines.get_all() if not m.archived),
                key=lambda m: (m.internal_name.lower(), m.id),
            )
        ordered_ids = list(widget.machine_ids)
        for pool in await self._pools.get_by_ids(list(widget.pool_ids)):
            ordered_ids.extend(m for m in pool.machine_ids if m not in ordered_ids)
        by_id = {m.id: m for m in await self._machines.get_by_ids(ordered_ids)}
        return [by_id[i] for i in ordered_ids if i in by_id and not by_id[i].archived]

    async def _board_pools(self, widget: MachineBoardWidget) -> list[MachinePool]:
        """The chosen pools, every active pool when nothing is chosen, and
        none when only machines are chosen."""
        if widget.pool_ids:
            by_id = {p.id: p for p in await self._pools.get_by_ids(list(widget.pool_ids))}
            return [by_id[i] for i in widget.pool_ids if i in by_id and not by_id[i].archived]
        if widget.machine_ids:
            return []
        return sorted(
            (p for p in await self._pools.get_all() if not p.archived),
            key=lambda p: (p.name.lower(), p.id),
        )

    async def _machine_board(
        self, widget: MachineBoardWidget, ctx: _FeedContext
    ) -> MachineBoardWidgetData:
        machines = await self._board_machines(widget)
        pools = await self._board_pools(widget)
        ids = [m.id for m in machines]
        wanted: list[int | None] = [*ids, None] if pools else list(ids)
        orders_by_machine: dict[int, list[ProductionOrder]] = {}
        waiting_by_pool: dict[int, list[ProductionOrder]] = {}
        pool_ids = {p.id for p in pools}
        for order in await self._repos.orders.get_live_by_machine_ids(wanted) if wanted else []:
            if order.machine_id is not None:
                orders_by_machine.setdefault(order.machine_id, []).append(order)
            elif order.machine_pool_id in pool_ids:
                waiting_by_pool.setdefault(order.machine_pool_id, []).append(order)

        shown: dict[int, tuple[ProductionOrder | None, list[ProductionOrder]]] = {
            m.id: rules.current_and_next(orders_by_machine.get(m.id, []), widget.next_count)
            for m in machines
        }
        await ctx.links.prefetch(
            ItemKind.MADE,
            [o.made_item_id for current, upcoming in shown.values() for o in upcoming]
            + [current.made_item_id for current, _ in shown.values() if current is not None]
            + [
                o.made_item_id
                for orders in waiting_by_pool.values()
                for o in orders[: widget.next_count]
            ],
        )
        return MachineBoardWidgetData(
            machines=await self._machine_rows(machines, orders_by_machine, shown, ctx),
            pools=[
                MachineBoardPool(
                    pool_id=pool.id,
                    pool_name=pool.name,
                    waiting=[
                        _order_card(o, ctx.links)
                        for o in waiting_by_pool.get(pool.id, [])[: widget.next_count]
                    ],
                    waiting_total=len(waiting_by_pool.get(pool.id, [])),
                )
                for pool in pools
            ],
        )

    async def _machine_rows(
        self,
        machines: list[ProductionMachine],
        orders_by_machine: dict[int, list[ProductionOrder]],
        shown: dict[int, tuple[ProductionOrder | None, list[ProductionOrder]]],
        ctx: _FeedContext,
    ) -> list[MachineBoardMachine]:
        ids = [m.id for m in machines]
        if not ids:
            return []
        downtimes = await self._downtimes.get_open_by_machine_ids(ids, started_by=ctx.now)
        production = await self._settings.get_production()
        calendars = await build_machine_calendars(
            ids,
            self._calendars,
            production.default_weekly_hours,
            zone=await tenant_zone(self._settings),
        )
        rows: list[MachineBoardMachine] = []
        for machine in machines:
            orders = orders_by_machine.get(machine.id, [])
            current, upcoming = shown[machine.id]
            downtime = downtimes.get(machine.id)
            calendar = calendars.get(machine.id)
            rows.append(
                MachineBoardMachine(
                    machine_id=machine.id,
                    machine_name=machine.internal_name,
                    state=rules.machine_state(
                        down=downtime is not None,
                        running=any(
                            o.status == ProductionOrderStatus.IN_PROGRESS.value for o in orders
                        ),
                        working_now=calendar is not None and rules.is_working_at(calendar, ctx.now),
                    ),
                    downtime_reason=downtime.reason if downtime is not None else None,
                    current=_order_card(current, ctx.links) if current is not None else None,
                    next=[_order_card(o, ctx.links) for o in upcoming],
                )
            )
        return rows

    # ── Lots ──────────────────────────────────────────────────────────

    async def _lot_ids_on_pools(self, pool_ids: tuple[int, ...]) -> set[int]:
        """Lots with a live order on a member of the pools or floating on
        one of them."""
        pools = await self._pools.get_by_ids(list(pool_ids))
        members = {m for pool in pools for m in pool.machine_ids}
        wanted: list[int | None] = [*sorted(members), None]
        return {
            o.lot_id
            for o in await self._repos.orders.get_live_by_machine_ids(wanted)
            if (o.machine_id is not None and o.machine_id in members)
            or (o.machine_pool_id is not None and o.machine_pool_id in pool_ids)
        }

    async def _lots_due(self, widget: LotsDueWidget, ctx: _FeedContext) -> LotsDueWidgetData:
        """Every open lot due on or before the horizon, overdue ones first.
        An overdue lot carries how many days it is past its target date."""
        _, lots = await self._repos.lots.get_multi(
            LotFilterDto(
                statuses=_OPEN_LOT_STATUSES,
                target_date_to=ctx.today + timedelta(days=widget.horizon_days),
                limit=_MAX_DUE_LOTS_READ,
            )
        )
        if widget.pool_ids:
            on_pools = await self._lot_ids_on_pools(widget.pool_ids)
            lots = [lot for lot in lots if lot.id in on_pools]
        targets = await describe_lot_target_dates(lots, self._repos)
        dated = sorted(
            (
                (target, lot)
                for lot in lots
                if (target := targets.get(lot.id, (None, None, None))[0]) is not None
            ),
            key=lambda pair: (pair[0], pair[1].lot_number),
        )[:_MAX_LOT_ROWS]
        await ctx.links.prefetch(ItemKind.MADE, [lot.made_item_id for _, lot in dated])
        return LotsDueWidgetData(
            lots=[
                _lot_row(
                    lot,
                    target,
                    rules.days_overdue(target, ctx.today),
                    widget.show_customer,
                    ctx.links,
                )
                for target, lot in dated
            ]
        )

    async def _late_lots(self, widget: LateLotsWidget, ctx: _FeedContext) -> LateLotsWidgetData:
        """The open lots the late lots KPI counts: projected to finish after
        their target date."""
        candidates = await self._kpi.get_late_lot_candidates(KpiScope())
        if not candidates:
            return LateLotsWidgetData(lots=[])
        lots = await self._repos.lots.get_by_ids([c.lot_id for c in candidates])
        lots_by_id = {lot.id: lot for lot in lots}
        targets = await describe_lot_target_dates(lots, self._repos)
        zone = await tenant_zone(self._settings)
        await ctx.links.prefetch(ItemKind.MADE, [lot.made_item_id for lot in lots])
        rows: list[InfoscreenLotRow] = []
        for candidate in candidates:
            lot = lots_by_id.get(candidate.lot_id)
            target = targets.get(candidate.lot_id, (None, None, None))[0]
            if (
                lot is None
                or target is None
                or candidate.effective_end is None
                or not is_lot_late(candidate.effective_end, target, zone)
            ):
                continue
            days_late = (candidate.effective_end.astimezone(zone).date() - target).days
            rows.append(_lot_row(lot, target, days_late, widget.show_customer, ctx.links))
        rows.sort(key=lambda r: (-(r.days_late or 0), r.lot_number))
        return LateLotsWidgetData(lots=rows[:_MAX_LOT_ROWS])

    # ── QA queue ──────────────────────────────────────────────────────

    async def _qa_queue(self, ctx: _FeedContext) -> QaQueueWidgetData:
        """The open inspection orders of the QA worklist, by planned start,
        undated ones last. A machineless inspection waits behind no other
        order, so its queue place says nothing about when it is due."""
        _, orders = await self._repos.orders.get_multi(
            ProductionOrderFilterDto(
                statuses=_OPEN_QA_STATUSES,
                step_role=StepRole.INSPECTION.value,
                limit=_MAX_QA_ROWS,
                order_by="planned_start",
                order_dir="asc",
            )
        )
        await ctx.links.prefetch(ItemKind.MADE, [o.made_item_id for o in orders])
        return QaQueueWidgetData(
            tasks=[
                InfoscreenQaRow(
                    task_id=o.id,
                    lot_number=o.lot_number or None,
                    part_number=o.made_item_part_number or None,
                    item_name=o.made_item_article_name or None,
                    status=o.status,
                    since=o.actual_start or o.planned_start,
                    thumbnail_url=ctx.links.url(ItemKind.MADE, o.made_item_id),
                )
                for o in orders
            ]
        )

    # ── Deliveries ────────────────────────────────────────────────────

    async def _deliveries(
        self, widget: DeliveriesExpectedWidget, ctx: _FeedContext
    ) -> DeliveriesExpectedWidgetData:
        """Open supplier lines expected from today to the horizon, with the
        overdue ones before them when the widget asks for them, oldest first.
        A line's own expected date wins over its order's."""
        today = ctx.today
        last_day = today + timedelta(days=widget.horizon_days)
        first_day = None if widget.show_overdue else today
        _, orders = await self._orders.get_multi(
            OrderFilterDto(
                status=_ORDERED_STATUSES,
                expected_delivery_from=first_day,
                expected_delivery_to=last_day,
                limit=_MAX_DELIVERY_ORDERS,
            )
        )
        if not orders:
            return DeliveriesExpectedWidgetData(deliveries=[])
        orders_by_id = {o.id: o for o in orders}
        lines: list[tuple[OrderItem, Order, date]] = []
        for item in await self._order_items.get_by_order_ids(list(orders_by_id)):
            order = orders_by_id.get(item.order_id)
            if order is None or item.status not in _ORDERED_ITEM_STATUSES:
                continue
            expected = item.expected_delivery_date or order.expected_delivery_date
            if (
                expected is not None
                and (first_day is None or first_day <= expected)
                and (expected <= last_day)
            ):
                lines.append((item, order, expected))
        lines.sort(key=lambda line: (line[2], line[1].order_number))
        lines = lines[:_MAX_DELIVERY_ROWS]
        line_items = [_line_item(item) for item, _, _ in lines]
        for item_kind in ItemKind:
            await ctx.links.prefetch(item_kind, [i for k, i in line_items if k is item_kind])
        rows: list[InfoscreenDeliveryRow] = []
        for (item, order, expected), (kind, item_id) in zip(lines, line_items, strict=True):
            open_quantity = max(item.quantity - item.quantity_delivered, 0.0)
            rows.append(
                InfoscreenDeliveryRow(
                    order_number=order.order_number,
                    part_number=item.item_part_number,
                    item_name=item.item_article_name or item.virtual_name or None,
                    quantity=open_quantity,
                    unit=item.unit or None,
                    supplier_name=item.supplier_name or order.supplier_name or None,
                    expected_date=expected,
                    days_late=rules.days_overdue(expected, today),
                    thumbnail_url=ctx.links.url(kind, item_id) if kind is not None else None,
                )
            )
        return DeliveriesExpectedWidgetData(deliveries=rows)

    # ── External work ─────────────────────────────────────────────────

    async def _external_work(
        self, widget: ExternalWorkWidget, ctx: _FeedContext
    ) -> ExternalWorkWidgetData:
        """The parts that must leave for a supplier from today to the
        horizon, with the overdue ones before them when the widget asks for
        them, as the procurement list of external work dates them. Parts
        already handed to the supplier have left and are not shown."""
        today = ctx.today
        page = await self._external_work_list.execute(
            ExternalWorkQuery(
                limit=_MAX_EXTERNAL_WORK_ROWS,
                latest_pickup_from=None if widget.show_overdue else today,
                latest_pickup_to=today + timedelta(days=widget.horizon_days),
                stages=list(_EXTERNAL_WORK_NOT_SENT),
                fabrication_method_ids=list(widget.fabrication_method_ids) or None,
                only_with_supplier=widget.only_with_supplier,
            )
        )
        await ctx.links.prefetch(ItemKind.MADE, [row.made_item_id for row in page.items])
        rows: list[InfoscreenExternalWorkRow] = []
        for row in page.items:
            on_order = row.order_item_id is not None
            alert = row.alert.value if row.alert in _EXTERNAL_WORK_ALERTS else None
            rows.append(
                InfoscreenExternalWorkRow(
                    lot_number=row.lot_number,
                    part_number=row.part_number or None,
                    item_name=row.article_name or None,
                    quantity=row.quantity,
                    methods=[
                        LocalizedText.of(method.name).resolve(ctx.language, ctx.default_language)
                        for method in row.fabrication_methods
                    ],
                    supplier_name=(row.supplier_name if on_order else row.suggested_supplier_name)
                    or None,
                    supplier_suggested=not on_order,
                    latest_pickup_date=row.latest_pickup_date,
                    ready_from=None if row.ready_now else row.planned_pickup_date,
                    ready_now=row.ready_now,
                    due_back_date=row.back_by_date,
                    alert=cast(Literal["not_ready_in_time", "overdue"] | None, alert),
                    days_late=(
                        rules.days_overdue(row.latest_pickup_date, today)
                        if row.latest_pickup_date is not None
                        else None
                    ),
                    thumbnail_url=ctx.links.url(ItemKind.MADE, row.made_item_id),
                )
            )
        return ExternalWorkWidgetData(rows=rows)

    # ── Weather ───────────────────────────────────────────────────────

    async def _weather_data(self, widget: WeatherWidget, ctx: _FeedContext) -> WeatherWidgetData:
        """The forecast for the widget's town, nothing when an admin switched
        the weather off or the service has nothing to give."""

        def without_forecast(status: Literal["unavailable", "off"]) -> WeatherWidgetData:
            return WeatherWidgetData(
                status=status,
                location_name=widget.location_name,
                region=widget.region,
                now=None,
                days=[],
                fetched_at=None,
                attribution=None,
            )

        if not (await self._settings.get_security()).enable_infoscreen_weather:
            return without_forecast("off")
        try:
            forecast = await self._weather.forecast(
                widget.latitude, widget.longitude, widget.days, ctx.timezone, ctx.weather_contact
            )
        except WeatherUnavailableError:
            return without_forecast("unavailable")
        return WeatherWidgetData(
            status="ok",
            location_name=widget.location_name,
            region=widget.region,
            now=InfoscreenWeatherNow(
                temperature=forecast.now.temperature,
                symbol=forecast.now.symbol,
                wind_speed=forecast.now.wind_speed,
                is_day=forecast.now.is_day,
            ),
            days=[
                InfoscreenWeatherDay(
                    date=day.day,
                    symbol=day.symbol,
                    temperature_max=day.temperature_max,
                    temperature_min=day.temperature_min,
                    precipitation_mm=day.precipitation_mm,
                )
                for day in forecast.days[: widget.days + 1]
            ],
            fetched_at=forecast.fetched_at,
            attribution=forecast.attribution,
        )

    # ── Products and projects ─────────────────────────────────────────

    async def _active_projects(self) -> list[Project]:
        _, projects = await self._projects.get_multi(
            ProjectFilterDto(
                status=ProjectStatus.ACTIVE.value,
                limit=_MAX_PROJECTS,
                order_by="project_number",
                order_dir="asc",
            )
        )
        return sorted(projects, key=lambda p: (p.project_number.lower(), p.id))

    async def _products_data(self, widget: ProductsWidget) -> ProductsWidgetData:
        """The active products by number, each with its active projects when
        the widget asks for them."""
        products = await self._products.get_active(_MAX_PRODUCTS)
        projects_by_product: dict[int, list[Project]] = {}
        if widget.show_projects:
            for project in await self._active_projects():
                if project.product_id is not None:
                    projects_by_product.setdefault(project.product_id, []).append(project)
        return ProductsWidgetData(
            products=[
                InfoscreenProductRow(
                    product_id=product.id,
                    product_number=product.product_number,
                    designation=product.designation or None,
                    description=product.description or None,
                    machine_type=product.machine_type or None,
                    customer_name=(
                        product.customer.name or None
                        if widget.show_customer and product.customer is not None
                        else None
                    ),
                    projects=[
                        InfoscreenProjectRef(
                            project_id=project.id,
                            project_number=project.project_number,
                            description=project.description or None,
                        )
                        for project in projects_by_product.get(product.id, [])
                    ],
                )
                for product in products
            ]
        )

    async def _projects_data(self, widget: ProjectsWidget) -> ProjectsWidgetData:
        """The active projects by number."""
        return ProjectsWidgetData(
            projects=[
                InfoscreenProjectRow(
                    project_id=project.id,
                    project_number=project.project_number,
                    description=project.description or None,
                    product_number=project.product.product_number if project.product else None,
                    product_designation=(
                        project.product.designation or None if project.product else None
                    ),
                    customer_name=(
                        project.customer.name or None
                        if widget.show_customer and project.customer is not None
                        else None
                    ),
                )
                for project in await self._active_projects()
            ]
        )

    # ── Machine detail ────────────────────────────────────────────────

    async def _machine_detail(
        self, widget: MachineDetailWidget, ctx: _FeedContext
    ) -> MachineDetailWidgetData:
        """The order on the machine now, or the next one when none is, with
        everything about it, and the orders after it as cards."""
        machine = next(iter(await self._machines.get_by_ids([widget.machine_id])), None)
        if machine is None or machine.archived:
            return MachineDetailWidgetData(
                machine_id=widget.machine_id,
                machine_name=None,
                state=None,
                downtime_reason=None,
                order=None,
                next=[],
            )
        orders = await self._repos.orders.get_live_by_machine_ids([machine.id])
        current, upcoming = rules.current_and_next(orders, widget.next_count + 1)
        shown = current if current is not None else next(iter(upcoming), None)
        following = [o for o in upcoming if o is not shown][: widget.next_count]
        await ctx.links.prefetch(ItemKind.MADE, [o.made_item_id for o in following])
        row = (
            await self._machine_rows(
                [machine], {machine.id: orders}, {machine.id: (current, [])}, ctx
            )
        )[0]
        return MachineDetailWidgetData(
            machine_id=machine.id,
            machine_name=machine.internal_name,
            state=row.state,
            downtime_reason=row.downtime_reason,
            order=(
                await self._machine_order(shown, shown is current, widget, ctx)
                if shown is not None
                else None
            ),
            next=[_order_card(o, ctx.links) for o in following],
        )

    async def _machine_order(
        self,
        order: ProductionOrder,
        is_current: bool,
        widget: MachineDetailWidget,
        ctx: _FeedContext,
    ) -> InfoscreenMachineOrder:
        lot = await self._repos.lots.get_by_id(order.lot_id) if order.lot_id else None
        item = await self._made_items.get_by_id(order.made_item_id)
        drawing_url = None
        if widget.show_drawing and item is not None and not item.archived:
            drawings = await self._made_item_files.get_by_item_id_and_category(
                item.id, MadeItemFileCategory.DRAWING
            )
            if drawings:
                drawing_url = ctx.links.drawing_url(item.id, drawings[0].id)
        return InfoscreenMachineOrder(
            production_order_id=order.id,
            current=is_current,
            status=order.status,
            lot_number=order.lot_number or None,
            part_number=order.made_item_part_number or None,
            item_name=order.made_item_article_name or None,
            revision=order.made_item_revision or None,
            material=order.made_item_material or None,
            mass_grams=order.made_item_mass,
            base_size=order.made_item_base_size or None,
            quantity=order.quantity,
            quantity_completed=order.quantity_completed,
            step_sequence=order.lot_position_sequence or None,
            step_count=order.lot_position_count or None,
            picture_url=await ctx.links.image_url(ItemKind.MADE, order.made_item_id),
            drawing_url=drawing_url,
            raw_material=self._raw_material(item, lot, ctx),
            lot=(
                InfoscreenMachineLot(
                    lot_id=lot.id,
                    lot_number=lot.lot_number,
                    status=lot.status.value,
                    quantity=lot.quantity,
                    project_number=lot.project_number or None,
                    customer_name=(lot.project_customer or None) if widget.show_customer else None,
                )
                if lot is not None
                else None
            ),
        )

    @staticmethod
    def _raw_material(
        item: MadeItem | None, lot: ProductionLot | None, ctx: _FeedContext
    ) -> InfoscreenRawMaterial | None:
        """What the item is made from, with how far the lot's input demand
        has come; None when the item names no input."""
        if item is None:
            return None
        demand_status = lot.demand_status.value if lot and lot.demand_status else None
        expected = lot.source_expected_delivery_date if lot else None
        if item.source_item is not None:
            source = item.source_item
            return InfoscreenRawMaterial(
                kind="source",
                part_number=None,
                name=source.type_name.resolve(ctx.language, ctx.default_language) or None,
                material=source.material or None,
                dimension=source.dimension or None,
                demand_status=demand_status,
                expected_delivery=expected,
            )
        if item.bought_item is not None:
            bought = item.bought_item
            return InfoscreenRawMaterial(
                kind="bought",
                part_number=bought.part_number or None,
                name=bought.article_name or None,
                material=None,
                dimension=None,
                demand_status=demand_status,
                expected_delivery=expected,
            )
        return None

    # ── Clock ─────────────────────────────────────────────────────────

    async def _next_holiday(self, today: date) -> InfoscreenHoliday | None:
        holiday = rules.next_holiday(await self._calendars.get_holidays(), today)
        if holiday is None:
            return None
        return InfoscreenHoliday(date=holiday.start_date, name=holiday.name)

    async def _bar_holiday(self, infoscreen: Infoscreen, today: date) -> InfoscreenHoliday | None:
        """The next holiday for the header or footer, when a shown bar has it."""
        if (infoscreen.show_header and infoscreen.header.shows_next_holiday) or (
            infoscreen.show_footer and infoscreen.footer.shows_next_holiday
        ):
            return await self._next_holiday(today)
        return None

    async def _clock(self, widget: ClockWidget, today: date) -> ClockWidgetData:
        if not widget.show_next_holiday:
            return ClockWidgetData(next_holiday=None)
        return ClockWidgetData(next_holiday=await self._next_holiday(today))
