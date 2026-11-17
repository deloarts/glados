"""
The planning read tools: the caller's briefing, the planning exceptions,
the schedule board and what runs on the shop floor now.
"""

from collections import Counter
from datetime import date
from datetime import timedelta
from typing import Any
from typing import Self

from pydantic import BaseModel
from pydantic import Field
from pydantic import model_validator

from src.modules.fulfillment.adapters.inbound.api.deps.dashboard import (
    get_dashboard_summary_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.dashboard import get_todo_sources_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_planning_exceptions_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import get_production_wip_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.production import get_qa_tasks_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.production import get_schedule_board_use_case
from src.modules.fulfillment.adapters.inbound.mcp.read_tools_common import limit_field
from src.modules.fulfillment.adapters.inbound.mcp.read_tools_common import pick
from src.modules.fulfillment.adapters.inbound.mcp.read_tools_common import tenant_today
from src.modules.fulfillment.application.dto.dashboard_dto import StatusCountResult
from src.modules.fulfillment.application.dto.production_schedule_dto import MachineCapacityDayResult
from src.modules.fulfillment.application.dto.production_schedule_dto import ScheduleBoardOrderResult
from src.modules.fulfillment.application.use_cases.production_order.get_qa_tasks import (
    QaTaskFilterDto,
)
from src.modules.fulfillment.domain.value_objects.planning_exception_kind import (
    PlanningExceptionKind,
)
from src.modules.platform.adapters.inbound.mcp.tools import AgentTool
from src.modules.platform.adapters.inbound.mcp.tools import AgentToolContext
from src.modules.platform.adapters.inbound.mcp.tools import ToolInput
from src.modules.platform.adapters.inbound.mcp.tools import ToolOutput

# The schedule tool reads at most this many days, a quarter, so its answer
# stays small; the web board itself reads up to two years.
MAX_SCHEDULE_DAYS = 92

_ORDER_FIELDS = (
    "id",
    "order_number",
    "status",
    "supplier_name",
    "ordered_date",
    "expected_delivery_date",
    "requested_at",
)
_BOUGHT_FIELDS = (
    "id",
    "status",
    "project_number",
    "item_order_code_1",
    "item_article_name",
    "quantity",
    "unit",
    "desired_delivery_date",
    "high_priority",
)
_MADE_FIELDS = (
    "id",
    "status",
    "project_number",
    "item_part_number",
    "item_revision",
    "item_article_name",
    "quantity",
    "unit",
    "desired_delivery_date",
    "high_priority",
)
_SOURCE_FIELDS = (
    "id",
    "status",
    "project_number",
    "lot_number",
    "quantity",
    "unit",
    "desired_delivery_date",
    "high_priority",
)
_LOT_FIELDS = (
    "id",
    "lot_number",
    "status",
    "priority",
    "project_number",
    "made_item_part_number",
    "made_item_article_name",
    "quantity",
    "quantity_completed",
    "target_date",
    "source_approval_status",
    "demand_status",
)
_BOARD_ORDER_FIELDS = (
    "order_id",
    "production_order_number",
    "lot_number",
    "project_number",
    "made_item_part_number",
    "made_item_revision",
    "quantity",
    "status",
    "pinned",
    "queue_sequence",
    "planned_start",
    "planned_end",
    "lot_position_sequence",
    "lot_position_count",
    "conflicts",
    "is_floating",
)
_QA_FIELDS = (
    "id",
    "production_order_number",
    "status",
    "priority",
    "quantity",
    "quantity_completed",
    "planned_start",
    "planned_end",
    "can_start",
    "conflicts",
    "inspection_method_name",
    "requires_evidence",
    "has_evidence",
    "lot_number",
    "lot_status",
    "made_item_part_number",
    "made_item_article_name",
    "project_number",
)


def _listed(rows: list[Any], fields: tuple[str, ...], limit: int) -> dict[str, Any]:
    return {"total": len(rows), "items": [pick(row, *fields) for row in rows[:limit]]}


def _counts(rows: list[StatusCountResult]) -> dict[str, int]:
    return {row.status: row.count for row in rows}


# ── my_briefing ──────────────────────────────────────────────────────────


class MyBriefingInput(ToolInput):
    include_lots: bool = Field(
        default=True,
        description="Include the lots, whose tasks belong to production planning.",
    )
    limit: int = limit_field(10)


async def _my_briefing(ctx: AgentToolContext, args: MyBriefingInput) -> ToolOutput:
    today, zone = await tenant_today(ctx)
    todo = await (await ctx.use_case(get_todo_sources_use_case)).execute(
        today, include_lots=args.include_lots
    )
    summary = await (await ctx.use_case(get_dashboard_summary_use_case)).execute(today, zone)
    exceptions = await (await ctx.use_case(get_planning_exceptions_use_case)).execute()
    return ToolOutput(
        {
            "today": today,
            "todo_horizon": todo.horizon,
            "todo": {
                "orders": _listed(todo.orders, _ORDER_FIELDS, args.limit),
                "bought_demands": _listed(todo.bought_demands, _BOUGHT_FIELDS, args.limit),
                "made_demands": _listed(todo.made_demands, _MADE_FIELDS, args.limit),
                "source_demands": _listed(todo.source_demands, _SOURCE_FIELDS, args.limit),
                "lots": _listed(todo.lots, _LOT_FIELDS, args.limit),
            },
            "planning_exceptions": {
                "total": len(exceptions),
                "by_kind": dict(Counter(e.kind.value for e in exceptions)),
                "items": exceptions[: args.limit],
            },
            "status_counts": {
                "lots": _counts(summary.lots),
                "bought_demands": _counts(summary.bought_demands),
                "made_demands": _counts(summary.made_demands),
                "source_demands": _counts(summary.source_demands),
            },
        }
    )


MY_BRIEFING = AgentTool(
    name="my_briefing",
    title="My briefing",
    description=(
        "What needs attention in planning and purchasing now: the orders, demands and lots "
        "that can give a task within the next week (the rows of the Todo page), the planning "
        "exceptions, and the status counts of lots and demands. Start here when asked what "
        "to do today or what is going wrong; follow up with the detail tools."
    ),
    input_model=MyBriefingInput,
    handler=_my_briefing,
)


# ── list_planning_exceptions ─────────────────────────────────────────────


class PlanningExceptionsInput(ToolInput):
    kind: PlanningExceptionKind | None = Field(
        default=None,
        description=(
            "Only this kind. lost_at_receipt and closed_short: a bought or raw material "
            "demand is open again because its order line lost pieces or was closed short. "
            "lot_ended_short: a made demand's lot was force completed below what it needs. "
            "material_short: a live lot's raw material is partly unallocated or waits on a "
            "line without a delivery date. late: a live lot is past its target date or "
            "planned to end after it."
        ),
    )
    project_number: str | None = Field(
        default=None, description="Only the rows of this project number, matched exactly."
    )
    limit: int = limit_field(50)


async def _list_planning_exceptions(
    ctx: AgentToolContext, args: PlanningExceptionsInput
) -> ToolOutput:
    rows = await (await ctx.use_case(get_planning_exceptions_use_case)).execute()
    if args.kind is not None:
        rows = [r for r in rows if r.kind == args.kind]
    if args.project_number:
        wanted = args.project_number.strip().casefold()
        rows = [r for r in rows if r.project_number.casefold() == wanted]
    return ToolOutput({"total": len(rows), "items": rows[: args.limit]})


LIST_PLANNING_EXCEPTIONS = AgentTool(
    name="list_planning_exceptions",
    title="Planning exceptions",
    description=(
        "The shortfalls and delays a planner must decide on, computed live: demands open "
        "again after lost pieces or a close short, made demands left short by a force "
        "completed lot, live lots short of raw material and live lots late against their "
        "target date. Sorted by kind, then the earliest target or oldest cause. Use "
        "explain_lot on a lot number for the reasons behind one row."
    ),
    input_model=PlanningExceptionsInput,
    handler=_list_planning_exceptions,
)


# ── schedule ─────────────────────────────────────────────────────────────


class ScheduleInput(ToolInput):
    date_from: date | None = Field(
        default=None, description="The first day of the window. Defaults to today."
    )
    days: int = Field(
        default=14,
        ge=1,
        le=MAX_SCHEDULE_DAYS,
        description="How many days the window covers, starting at date_from.",
    )
    machine: str | None = Field(
        default=None,
        description="Only machines whose internal name contains this text, ignoring case.",
    )
    pool: str | None = Field(
        default=None,
        description="Only machine pools whose name contains this text, ignoring case.",
    )
    include_unassigned: bool | None = Field(
        default=None,
        description=(
            "Include the production orders on no machine or pool yet. Defaults to true "
            "unless a machine or pool is named."
        ),
    )
    limit: int = limit_field(20, "production orders per machine or pool")

    @model_validator(mode="after")
    def _one_filter(self) -> Self:
        if self.machine and self.pool:
            raise ValueError("Name a machine or a pool, not both.")
        return self


def _capacity(days: list[MachineCapacityDayResult]) -> dict[str, Any]:
    return {
        "booked_minutes": sum(d.booked_minutes for d in days),
        "available_minutes": sum(d.available_minutes for d in days),
        "overbooked_days": [
            {"date": d.date, "overbooked_minutes": d.overbooked_minutes}
            for d in days
            if d.overbooked_minutes > 0
        ],
    }


def _orders(orders: list[ScheduleBoardOrderResult], limit: int) -> dict[str, Any]:
    return _listed(orders, _BOARD_ORDER_FIELDS, limit)


def _matches(name: str, wanted: str | None) -> bool:
    return wanted is None or wanted.strip().casefold() in name.casefold()


async def _schedule(ctx: AgentToolContext, args: ScheduleInput) -> ToolOutput:
    date_from = args.date_from or (await tenant_today(ctx))[0]
    date_to = date_from + timedelta(days=args.days - 1)
    board = await (await ctx.use_case(get_schedule_board_use_case)).execute(
        date_from=date_from, date_to=date_to
    )
    machines = (
        []
        if args.pool
        else [m for m in board.machines if _matches(m.machine_internal_name, args.machine)]
    )
    pools = [] if args.machine else [p for p in board.pools if _matches(p.pool_name, args.pool)]
    unassigned = args.include_unassigned
    if unassigned is None:
        unassigned = not args.machine and not args.pool
    data: dict[str, Any] = {
        "date_from": date_from,
        "date_to": date_to,
        "stale_since": board.stale_since,
        "machines": [
            {
                "machine_id": m.machine_id,
                "machine_internal_name": m.machine_internal_name,
                "capacity": _capacity(m.capacity),
                "orders": _orders(m.orders, args.limit),
            }
            for m in machines
        ],
        "pools": [
            {
                "pool_id": p.pool_id,
                "pool_name": p.pool_name,
                "machine_ids": p.machine_ids,
                "capacity": _capacity(p.capacity),
                "orders": _orders(p.orders, args.limit),
            }
            for p in pools
        ],
    }
    if unassigned:
        data["unassigned"] = _orders(board.unassigned, args.limit)
    return ToolOutput(data)


SCHEDULE = AgentTool(
    name="schedule",
    title="Schedule board",
    description=(
        "The production schedule for a window of days, as the schedule board shows it: per "
        "machine and per machine pool the booked and available minutes, the overbooked days "
        "and the production orders with their planned start and end, queue position, pin "
        "and conflicts, plus the orders on no machine yet. Narrow it to one machine or pool "
        "by name. The board is computed on read and never changes the plan."
    ),
    input_model=ScheduleInput,
    handler=_schedule,
)


# ── shop_floor_now ───────────────────────────────────────────────────────


class ShopFloorInput(ToolInput):
    include_future_qa: bool = Field(
        default=False,
        description="Also list the QA tasks that cannot be worked yet because an earlier step is open.",
    )
    limit: int = limit_field()


def _wip(row: BaseModel) -> dict[str, Any]:
    return row.model_dump(mode="json", exclude={"public_id"})


async def _shop_floor_now(ctx: AgentToolContext, args: ShopFloorInput) -> ToolOutput:
    wip = await (await ctx.use_case(get_production_wip_use_case)).execute()
    qa_total, qa = await (await ctx.use_case(get_qa_tasks_use_case)).execute(
        QaTaskFilterDto(include_future=args.include_future_qa, skip=0, limit=args.limit)
    )
    return ToolOutput(
        {
            "work_in_progress": {
                "total": len(wip),
                "items": [_wip(row) for row in wip[: args.limit]],
            },
            "qa_tasks": {"total": qa_total, "items": [pick(t, *_QA_FIELDS) for t in qa]},
        }
    )


SHOP_FLOOR_NOW = AgentTool(
    name="shop_floor_now",
    title="Shop floor now",
    description=(
        "What is in production right now: every lot in work with the piece counts of each "
        "of its stages and the machines or suppliers holding them, and the open QA tasks "
        "with their inspection method and whether the required evidence is on file."
    ),
    input_model=ShopFloorInput,
    handler=_shop_floor_now,
)
