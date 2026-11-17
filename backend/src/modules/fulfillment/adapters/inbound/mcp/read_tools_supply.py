"""
The supply read tools: how a project's or an item's demands are covered,
the supplier orders and their open lines, and the offers of a quote
request side by side.
"""

from datetime import timedelta
from typing import Any
from typing import Literal
from typing import Self

from pydantic import Field
from pydantic import model_validator

from src.modules.fulfillment.adapters.inbound.api.deps.demands import get_demand_items_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_demand_summary_batch_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_made_item_demand_summary_batch_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.demands import get_made_item_demands_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_source_item_demand_summary_batch_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_source_item_demands_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.orders import get_orders_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.quote_requests import (
    get_quote_requests_use_case,
)
from src.modules.fulfillment.adapters.inbound.mcp.read_tools_common import limit_field
from src.modules.fulfillment.adapters.inbound.mcp.read_tools_common import pick
from src.modules.fulfillment.adapters.inbound.mcp.read_tools_common import tenant_today
from src.modules.fulfillment.application.dto.order_dto import OrderItemResult
from src.modules.fulfillment.application.dto.order_dto import OrderResult
from src.modules.fulfillment.application.dto.quote_request_dto import QuoteRequestResult
from src.modules.fulfillment.application.dto.source_item_demand_dto import SourceItemDemandResult
from src.modules.fulfillment.domain.errors import QuoteRequestNotFoundError
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.quote_request_status import QuoteRequestStatus
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    DemandItemFilterDto,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    MadeItemDemandFilterDto,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import OrderFilterDto
from src.modules.fulfillment.ports.outbound.repositories.quote_request_repository import (
    QuoteRequestFilterDto,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    SourceItemDemandFilterDto,
)
from src.modules.platform.adapters.inbound.mcp.tools import AgentTool
from src.modules.platform.adapters.inbound.mcp.tools import AgentToolContext
from src.modules.platform.adapters.inbound.mcp.tools import ToolInput
from src.modules.platform.adapters.inbound.mcp.tools import ToolOutput
from src.modules.platform.const import MAX_PAGE_SIZE
from src.modules.platform.infrastructure.label_languages import resolve_label

DemandFamily = Literal["bought", "made", "source"]
_ALL_FAMILIES: tuple[DemandFamily, ...] = ("bought", "made", "source")

_COVERAGE_FIELDS = (
    "allocated",
    "fulfilled_from_stock",
    "ordered",
    "delivered",
    "remaining",
    "unallocated",
    "pending",
    "in_transit",
    "is_fully_allocated",
    "is_fully_delivered",
    "unit_mismatch",
    "order_numbers",
    "lot_ids",
)
_DEMAND_FIELDS = (
    "id",
    "status",
    "project_number",
    "quantity",
    "unit",
    "desired_delivery_date",
    "high_priority",
    "canceled_at",
    "fulfilled_manually_at",
)
_OPEN_LINE_STATUSES = frozenset(
    {
        OrderItemStatus.PENDING,
        OrderItemStatus.REQUESTED,
        OrderItemStatus.ORDERED,
        OrderItemStatus.PARTIALLY_DELIVERED,
    }
)
_ORDER_FIELDS = (
    "id",
    "order_number",
    "status",
    "supplier_name",
    "note",
    "ordered_date",
    "expected_delivery_date",
    "delivery_date",
    "storage_place",
    "requested_at",
    "canceled_at",
)
_LINE_FIELDS = (
    "position",
    "status",
    "item_order_code_1",
    "item_article_name",
    "item_part_number",
    "item_material",
    "item_dimension",
    "quantity",
    "quantity_delivered",
    "quantity_rejected",
    "unit",
    "price",
    "expected_delivery_date",
    "expected_pickup_date",
    "ready_for_pickup_date",
    "delivery_date",
    "project_number",
    "quote_request_number",
)


# ── demand_coverage ──────────────────────────────────────────────────────


class DemandCoverageInput(ToolInput):
    project_number: str | None = Field(
        default=None,
        description=(
            "The project number. Matches every project number that contains this text, as the "
            "demand lists do; each row names its project."
        ),
    )
    part_number: str | None = Field(
        default=None,
        description=(
            "The part number of a bought or made item, matched as text it contains. Raw "
            "material demands have no part number and are left out when only this is given."
        ),
    )
    families: list[DemandFamily] = Field(
        default_factory=lambda: list(_ALL_FAMILIES),
        description=(
            "The demand families to read: bought items, made items and raw material (source) "
            "for lots."
        ),
    )
    include_finished: bool = Field(
        default=False, description="Also list the fulfilled and canceled demands."
    )
    limit: int = limit_field(20, "demands per family")

    @model_validator(mode="after")
    def _something_to_look_for(self) -> Self:
        if not (self.project_number or "").strip() and not (self.part_number or "").strip():
            raise ValueError("Give a project_number, a part_number or both.")
        return self


def _covered(row: dict[str, Any], summary: Any) -> dict[str, Any]:
    row["coverage"] = pick(summary, *_COVERAGE_FIELDS) if summary is not None else None
    return row


def _source_label(demand: SourceItemDemandResult) -> dict[str, Any]:
    if demand.source_item is not None:
        return {
            "material": demand.source_item.material,
            "dimension": demand.source_item.dimension,
            "type_name": resolve_label(demand.source_item.type_name),
        }
    if demand.bought_item is not None:
        return {
            "item_order_code_1": demand.bought_item.order_code_1,
            "item_article_name": demand.bought_item.article_name,
        }
    return {}


async def _demand_coverage(ctx: AgentToolContext, args: DemandCoverageInput) -> ToolOutput:
    project = (args.project_number or "").strip() or None
    part = (args.part_number or "").strip() or None
    finished = None if args.include_finished else True
    data: dict[str, Any] = {}

    if "bought" in args.families:
        page = await (await ctx.use_case(get_demand_items_use_case)).execute(
            DemandItemFilterDto(
                skip=0,
                limit=args.limit,
                project_number=project,
                item_part_number=part,
                ignore_fulfilled=finished,
                ignore_canceled=finished,
                order_by="desired_delivery_date",
                order_dir="asc",
            )
        )
        summaries = await (await ctx.use_case(get_demand_summary_batch_use_case)).execute(
            demand_item_ids=[d.id for d in page.items]
        )
        data["bought"] = {
            "total": page.total,
            "items": [
                _covered(
                    {
                        **pick(d, *_DEMAND_FIELDS),
                        "item_part_number": d.item.part_number if d.item else None,
                        "item_order_code_1": d.item_order_code_1,
                        "item_article_name": d.item_article_name,
                    },
                    summaries.get(d.id),
                )
                for d in page.items
            ],
        }

    if "made" in args.families:
        made = await (await ctx.use_case(get_made_item_demands_use_case)).execute(
            MadeItemDemandFilterDto(
                skip=0,
                limit=args.limit,
                project_number=project,
                item_part_number=part,
                ignore_fulfilled=finished,
                ignore_canceled=finished,
                order_by="desired_delivery_date",
                order_dir="asc",
            )
        )
        made_summaries = await (
            await ctx.use_case(get_made_item_demand_summary_batch_use_case)
        ).execute(demand_item_ids=[d.id for d in made.items])
        data["made"] = {
            "total": made.total,
            "items": [
                _covered(
                    pick(
                        d,
                        *_DEMAND_FIELDS,
                        "item_part_number",
                        "item_revision",
                        "item_article_name",
                        "is_alteration",
                    ),
                    made_summaries.get(d.id),
                )
                for d in made.items
            ],
        }

    if "source" in args.families and project is not None:
        source = await (await ctx.use_case(get_source_item_demands_use_case)).execute(
            SourceItemDemandFilterDto(
                skip=0,
                limit=args.limit,
                project_number=project,
                ignore_fulfilled=finished,
                ignore_canceled=finished,
                order_by="desired_delivery_date",
                order_dir="asc",
            )
        )
        source_summaries = await (
            await ctx.use_case(get_source_item_demand_summary_batch_use_case)
        ).execute(demand_item_ids=[d.id for d in source.items])
        data["source"] = {
            "total": source.total,
            "items": [
                _covered(
                    {**pick(d, *_DEMAND_FIELDS, "lot_number"), **_source_label(d)},
                    source_summaries.get(d.id),
                )
                for d in source.items
            ],
        }
    return ToolOutput(data)


DEMAND_COVERAGE = AgentTool(
    name="demand_coverage",
    title="Demand coverage",
    description=(
        "How the demands of a project, or of a bought or made part, are covered: for each "
        "bought item demand, made item demand and raw material demand its status, the "
        "quantity allocated, ordered, delivered and taken from stock, what remains and is "
        "still unallocated, and the orders or lots covering it. Earliest desired date first. "
        "Use it to check whether a project's parts will arrive or what still needs ordering."
    ),
    input_model=DemandCoverageInput,
    handler=_demand_coverage,
)


# ── orders ───────────────────────────────────────────────────────────────


class OrdersInput(ToolInput):
    order_number: str | None = Field(
        default=None, description="Only orders whose number contains this text."
    )
    search: str | None = Field(
        default=None, description="Free text, matched as the search box of the orders list."
    )
    statuses: list[OrderStatus] | None = Field(
        default=None, description="Only orders in one of these statuses."
    )
    overdue_only: bool = Field(
        default=False,
        description=(
            "Only orders with an open line whose expected delivery date has passed, the "
            "longest overdue first."
        ),
    )
    open_lines_only: bool = Field(
        default=True,
        description="List only the lines not yet delivered or canceled under each order.",
    )
    limit: int = limit_field(20, "orders")


def _line(line: OrderItemResult, today: Any) -> dict[str, Any]:
    row = pick(line, *_LINE_FIELDS)
    row["overdue"] = (
        line.status in _OPEN_LINE_STATUSES
        and line.expected_delivery_date is not None
        and line.expected_delivery_date < today
    )
    return row


def _order(order: OrderResult, today: Any, open_lines_only: bool) -> dict[str, Any]:
    lines = [
        line for line in order.items if not open_lines_only or line.status in _OPEN_LINE_STATUSES
    ]
    return {
        **pick(order, *_ORDER_FIELDS),
        "net_total": order.net_total,
        "line_count": len(order.items),
        "lines": [_line(line, today) for line in sorted(lines, key=lambda li: li.position)],
    }


async def _orders(ctx: AgentToolContext, args: OrdersInput) -> ToolOutput:
    today, _ = await tenant_today(ctx)
    use_case = await ctx.use_case(get_orders_use_case)
    statuses = [s.value for s in args.statuses] if args.statuses else None
    if not args.overdue_only:
        page = await use_case.get_many(
            OrderFilterDto(
                skip=0,
                limit=args.limit,
                status=statuses,
                order_number=args.order_number,
                search=args.search,
            )
        )
        items = [_order(o, today, args.open_lines_only) for o in page.items]
        return ToolOutput({"total": page.total, "items": items})

    # The Todo page's filter keeps the orders with an open line expected by
    # its horizon; with yesterday as the horizon every overdue order is in
    # it, beside drafts and pickups, which the line check below drops.
    page = await use_case.get_many(
        OrderFilterDto(
            skip=0,
            limit=MAX_PAGE_SIZE,
            status=statuses,
            order_number=args.order_number,
            search=args.search,
            todo_horizon=today - timedelta(days=1),
        )
    )
    overdue: list[tuple[Any, dict[str, Any]]] = []
    for order in page.items:
        row = _order(order, today, args.open_lines_only)
        late = [line for line in row["lines"] if line["overdue"]]
        if late:
            overdue.append((min(line["expected_delivery_date"] for line in late), row))
    overdue.sort(key=lambda pair: pair[0])
    return ToolOutput({"total": len(overdue), "items": [row for _, row in overdue[: args.limit]]})


ORDERS = AgentTool(
    name="orders",
    title="Supplier orders",
    description=(
        "Supplier purchase orders with their lines: status, supplier, ordered and expected "
        "delivery dates, and per line the item, quantities ordered and delivered, the "
        "expected delivery and whether it is overdue. Filter by order number, status or free "
        "text, or ask for overdue deliveries only. Newest orders first."
    ),
    input_model=OrdersInput,
    handler=_orders,
)


# ── compare_offers ───────────────────────────────────────────────────────


class CompareOffersInput(ToolInput):
    request_number: str | None = Field(
        default=None,
        description=(
            "The quote request number. Without it the tool lists the quote requests so you "
            "can pick one."
        ),
    )
    statuses: list[QuoteRequestStatus] = Field(
        default_factory=lambda: [QuoteRequestStatus.DRAFT, QuoteRequestStatus.SENT],
        description="When listing, only requests in one of these statuses.",
    )
    limit: int = limit_field(20, "quote requests")


def _request_summary(request: QuoteRequestResult) -> dict[str, Any]:
    return {
        **pick(request, "id", "request_number", "status", "deadline", "note", "created"),
        "line_count": len(request.lines),
        "open_line_count": sum(1 for line in request.lines if line.state == "open"),
        "supplier_count": len(request.suppliers),
        "responded_count": sum(1 for s in request.suppliers if s.responded_at is not None),
    }


def _side_by_side(request: QuoteRequestResult) -> dict[str, Any]:
    offers_by_line: dict[int, list[dict[str, Any]]] = {line.id: [] for line in request.lines}
    for supplier in request.suppliers:
        for quote in supplier.quotes:
            offers_by_line.setdefault(quote.line_id, []).append(
                {
                    "supplier_row_id": supplier.id,
                    "supplier_id": supplier.supplier_id,
                    "supplier_name": supplier.supplier_name,
                    **pick(
                        quote,
                        "unit_price",
                        "no_offer",
                        "lead_time_days",
                        "min_quantity",
                        "note",
                        "substitute_item_name",
                        "substitute_item_code",
                        "substitute_reason",
                    ),
                }
            )
    return {
        **_request_summary(request),
        "cheapest_complete_supplier_row_id": request.cheapest_complete_supplier_id,
        "lines": [
            {
                "line_id": line.id,
                **pick(
                    line,
                    "position",
                    "line_type",
                    "item_name",
                    "item_code",
                    "quantity",
                    "unit",
                    "project_number",
                    "lot_number",
                    "state",
                    "awarded_supplier_id",
                    "awarded_price",
                    "order_number",
                    "note",
                ),
                "cheapest_supplier_row_id": line.cheapest_supplier_id,
                "offers": offers_by_line.get(line.id, []),
            }
            for line in sorted(request.lines, key=lambda li: li.position)
        ],
        "suppliers": [
            {
                "supplier_row_id": s.id,
                **pick(
                    s,
                    "supplier_id",
                    "supplier_name",
                    "sent_at",
                    "responded_at",
                    "declined_at",
                    "valid_until",
                    "note",
                    "priced_lines",
                    "extra_costs",
                    "has_awarded_lines",
                    "not_asked_line_ids",
                ),
                "lines_total": s.lines_total,
                "extra_costs_total": s.extra_costs_total,
                # Every list result names its row count `total`, so the
                # supplier's sum is named as the money it is.
                "total_price": s.total,
            }
            for s in sorted(request.suppliers, key=lambda row: row.position)
        ],
    }


async def _compare_offers(ctx: AgentToolContext, args: CompareOffersInput) -> ToolOutput:
    use_case = await ctx.use_case(get_quote_requests_use_case)
    if args.request_number is None or not args.request_number.strip():
        page = await use_case.get_many(
            ctx.actor,
            QuoteRequestFilterDto(
                skip=0,
                limit=args.limit,
                status=[s.value for s in args.statuses] or None,
                order_by="id",
                order_dir="desc",
            ),
        )
        return ToolOutput({"total": page.total, "items": [_request_summary(r) for r in page.items]})

    number = args.request_number.strip()
    page = await use_case.get_many(ctx.actor, QuoteRequestFilterDto(search=number, limit=10))
    for request in page.items:
        if request.request_number.casefold() == number.casefold():
            return ToolOutput(_side_by_side(request))
    similar = ", ".join(r.request_number for r in page.items)
    raise QuoteRequestNotFoundError(
        f"No quote request is numbered {number!r}."
        + (f" Similar numbers: {similar}." if similar else "")
    )


COMPARE_OFFERS = AgentTool(
    name="compare_offers",
    title="Compare offers",
    description=(
        "The offers of one quote request side by side: per line the item, quantity, state "
        "and award, and every supplier's answer for it with lead time, minimum quantity, no "
        "offer or an alternative item; per supplier when it was asked and answered and how "
        "many lines it priced. Prices appear only where the administrator lets agents see "
        "costs. Without a request number it lists the open quote requests."
    ),
    input_model=CompareOffersInput,
    handler=_compare_offers,
)
