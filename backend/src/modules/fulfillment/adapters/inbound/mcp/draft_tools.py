"""
The draft tools of Planning and fulfillment. Each tool prepares one record
that waits for a person in Glados: a DRAFT purchase order, a DRAFT quote
request or a DRAFT production lot. A tool runs the same create use cases,
built through the same dependency factories, as the web app's panels that
create these records from selected demands, and nothing else. It never
places or requests an order, never sends a quote request and never plans,
releases or completes a lot; the person reviews the draft in Glados and
commits, sends or deletes it there.

As in those panels, a demand takes the share of a line or lot that it still
lacks, its unallocated quantity, and the demands of one item, unit and
project share one line. A demand that is fulfilled, canceled or already
fully covered is refused before anything is written.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from dataclasses import field
from datetime import date
from typing import Self

from pydantic import Field
from pydantic import model_validator

from src.modules.fulfillment.adapters.inbound.api.deps.demands import get_demand_item_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.demands import get_demand_summary_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_made_item_demand_summary_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.demands import get_made_item_demand_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_source_item_demand_summary_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_source_item_demand_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.lots import get_create_lot_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.orders import get_create_order_item_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.orders import get_create_order_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.orders import get_order_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.quote_requests import (
    get_create_quote_request_use_case,
)
from src.modules.fulfillment.application.dto.order_dto import CreateOrderCommand
from src.modules.fulfillment.application.dto.order_dto import CreateOrderItemCommand
from src.modules.fulfillment.application.dto.order_dto import OrderLineDemandAllocationInput
from src.modules.fulfillment.application.dto.production_lot_dto import CreateLotCommand
from src.modules.fulfillment.application.dto.production_lot_dto import LotDemandAllocationInput
from src.modules.fulfillment.application.dto.quote_request_dto import CreateQuoteRequestCommand
from src.modules.fulfillment.application.dto.quote_request_dto import QuoteRequestLineDemandInput
from src.modules.fulfillment.application.dto.quote_request_dto import QuoteRequestLineInput
from src.modules.fulfillment.domain.services.allocation_service import BoughtItemAllocationRules
from src.modules.fulfillment.domain.services.made_item_demand_rules import MadeItemAllocationRules
from src.modules.fulfillment.domain.services.source_item_allocation_service import (
    SourceItemAllocationRules,
)
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.quote_request_status import (
    QuoteRequestDemandFamily,
)
from src.modules.platform.adapters.inbound.mcp.tools import AgentTool
from src.modules.platform.adapters.inbound.mcp.tools import AgentToolContext
from src.modules.platform.adapters.inbound.mcp.tools import DraftToolInput
from src.modules.platform.adapters.inbound.mcp.tools import ToolKind
from src.modules.platform.adapters.inbound.mcp.tools import ToolOutput
from src.modules.platform.adapters.inbound.mcp.tools import ref
from src.modules.platform.domain.exceptions import DomainError
from src.modules.platform.domain.exceptions import InvalidInputError
from src.modules.platform.domain.value_objects.permission import Permission

# Below this a demand counts as fully covered, as in the web app's panels.
_EPSILON = 1e-6
_MAX_DEMANDS = 100

_DEMAND_IDS_HINT = (
    "Integer demand ids as the demand read tools show them. Only demands that are neither "
    "fulfilled nor canceled and still lack pieces are accepted."
)


# ── Demands into lines ────────────────────────────────────────────────


@dataclass
class _Share:
    family: QuoteRequestDemandFamily
    demand_id: int
    quantity: float


@dataclass
class _Line:
    """The demands of one item, unit and project, which one line covers."""

    bought_item_id: int | None
    source_item_id: int | None
    project_id: int
    unit: str
    shares: list[_Share] = field(default_factory=list)
    desired: date | None = None

    @property
    def quantity(self) -> float:
        return round(sum(share.quantity for share in self.shares), 6)

    @property
    def demand_ids(self) -> list[int]:
        return [share.demand_id for share in self.shares]


# The family, bought item, source item, unit and project a line is for.
type _LineKey = tuple[str, int | None, int | None, str, int]


def _earlier(first: date | None, second: date | None) -> date | None:
    if first is None or second is None:
        return first or second
    return min(first, second)


def _assert_lacks_pieces(noun: str, demand_id: int, unallocated: float) -> float:
    if unallocated <= _EPSILON:
        raise InvalidInputError(
            f"{noun} #{demand_id} is fully covered already; there is nothing left to draft for it."
        )
    return round(unallocated, 6)


async def _demand_lines(
    ctx: AgentToolContext, bought_ids: Iterable[int], source_ids: Iterable[int]
) -> list[_Line]:
    """The lines the open bought and source demands need, grouped by item,
    unit and project and in the order the demands were named. Reads each
    demand and its quantity summary through the web app's read use cases."""
    lines: dict[_LineKey, _Line] = {}

    reader = await ctx.use_case(get_demand_item_use_case)
    summaries = await ctx.use_case(get_demand_summary_use_case)
    for demand_id in bought_ids:
        demand = await reader.execute(demand_id=demand_id)
        BoughtItemAllocationRules.assert_not_terminal(demand)
        share = _assert_lacks_pieces(
            "Bought item demand",
            demand_id,
            (await summaries.execute(demand_item_id=demand_id)).unallocated,
        )
        key: _LineKey = ("bought", demand.item_id, None, demand.unit, demand.project_id)
        line = lines.setdefault(key, _Line(demand.item_id, None, demand.project_id, demand.unit))
        line.shares.append(_Share(QuoteRequestDemandFamily.BOUGHT, demand_id, share))
        line.desired = _earlier(line.desired, demand.desired_delivery_date)

    source_reader = await ctx.use_case(get_source_item_demand_use_case)
    source_summaries = await ctx.use_case(get_source_item_demand_summary_use_case)
    for demand_id in source_ids:
        source = await source_reader.execute(demand_id=demand_id)
        SourceItemAllocationRules.assert_not_terminal(source)
        share = _assert_lacks_pieces(
            "Source item demand",
            demand_id,
            (await source_summaries.execute(demand_item_id=demand_id)).unallocated,
        )
        # A material demand names a bought item or a source item; a line
        # names exactly one, the bought item first, as the web panel does.
        bought_item_id = source.bought_item_id
        source_item_id = source.source_item_id if bought_item_id is None else None
        key = ("source", bought_item_id, source_item_id, source.unit, source.project_id)
        line = lines.setdefault(
            key, _Line(bought_item_id, source_item_id, source.project_id, source.unit)
        )
        line.shares.append(_Share(QuoteRequestDemandFamily.SOURCE, demand_id, share))
    return list(lines.values())


class _DemandSelection(DraftToolInput):
    bought_demand_ids: list[int] = Field(
        default_factory=list,
        max_length=_MAX_DEMANDS,
        description=f"Bought item demands to cover. {_DEMAND_IDS_HINT}",
    )
    source_demand_ids: list[int] = Field(
        default_factory=list,
        max_length=_MAX_DEMANDS,
        description=f"Source item (raw material) demands to cover. {_DEMAND_IDS_HINT}",
    )

    @model_validator(mode="after")
    def _some_demands_once_each(self) -> Self:
        if not self.bought_demand_ids and not self.source_demand_ids:
            raise ValueError("Name at least one bought or source item demand.")
        for ids in (self.bought_demand_ids, self.source_demand_ids):
            if len(ids) != len(set(ids)):
                raise ValueError("Name each demand once.")
        return self


# ── draft_purchase_order ──────────────────────────────────────────────


class DraftPurchaseOrderInput(_DemandSelection):
    supplier_id: int = Field(
        gt=0, description="The id of the supplier the order is for, as the read tools show it."
    )
    note: str | None = Field(
        default=None, max_length=2000, description="An optional note on the order for the buyer."
    )


async def _draft_purchase_order(ctx: AgentToolContext, args: DraftPurchaseOrderInput) -> ToolOutput:
    lines = await _demand_lines(ctx, args.bought_demand_ids, args.source_demand_ids)

    create_order = await ctx.use_case(get_create_order_use_case)
    order = await create_order.execute(
        actor=ctx.actor, cmd=CreateOrderCommand(supplier_id=args.supplier_id, note=args.note)
    )
    created = [ref("order", order.public_id)]

    # Every line is its own use case call with its own commit, as the web
    # panel adds them one request at a time, so each line gets a use case
    # wired afresh, with a reconciler and lock plan of its own.
    added: list[dict[str, object]] = []
    failure: str | None = None
    for line in lines:
        create_line = await ctx.use_case(get_create_order_item_use_case)
        allocations = [
            OrderLineDemandAllocationInput(demand_item_id=s.demand_id, quantity=s.quantity)
            for s in line.shares
        ]
        is_source = line.shares[0].family is QuoteRequestDemandFamily.SOURCE
        try:
            item = await create_line.execute(
                actor=ctx.actor,
                cmd=CreateOrderItemCommand(
                    order_id=order.id,
                    supplier_id=args.supplier_id,
                    project_id=line.project_id,
                    bought_item_id=line.bought_item_id,
                    source_item_id=line.source_item_id,
                    quantity=line.quantity,
                    unit=line.unit,
                    items_per_unit=1.0,
                    expected_delivery_date=line.desired,
                    bought_demand_allocations=[] if is_source else allocations,
                    source_demand_allocations=allocations if is_source else [],
                ),
            )
        except DomainError as e:
            # The order and the lines before this one are committed. A draft
            # with fewer lines is still only a draft, so it stays for the
            # person to finish or delete, and the call reports what exists.
            await ctx.db.rollback()
            failure = f"Line for demands {line.demand_ids} was refused: {e}"
            break
        created.append(ref("order_item", item.public_id))
        added.append(
            {
                "public_id": str(item.public_id),
                "bought_item_id": item.bought_item_id,
                "source_item_id": item.source_item_id,
                "quantity": item.quantity,
                "unit": item.unit,
                "demand_ids": line.demand_ids,
            }
        )

    stored = await (await ctx.use_case(get_order_use_case)).get_one(order_id=order.id)
    data: dict[str, object] = {
        "order": {
            "public_id": str(stored.public_id),
            "order_number": stored.order_number,
            "status": stored.status,
            "supplier_id": stored.supplier_id,
            "supplier_name": stored.supplier_name,
            "lines": added,
        },
        "complete": failure is None,
        "next_step": (
            "A person reviews this draft order in Glados and places it there. Nothing was "
            "ordered or sent."
        ),
    }
    if failure is not None:
        data["error"] = failure
    return ToolOutput(data, created_refs=created)


# ── draft_quote_request ───────────────────────────────────────────────


class DraftQuoteRequestInput(_DemandSelection):
    supplier_ids: list[int] = Field(
        min_length=1,
        max_length=50,
        description="The ids of the suppliers to ask for an offer, as the read tools show them.",
    )
    deadline: date | None = Field(
        default=None, description="The day by which the suppliers should answer, if any."
    )
    note: str | None = Field(
        default=None, max_length=2000, description="An optional note on the request."
    )


async def _draft_quote_request(ctx: AgentToolContext, args: DraftQuoteRequestInput) -> ToolOutput:
    lines = await _demand_lines(ctx, args.bought_demand_ids, args.source_demand_ids)
    cmd = CreateQuoteRequestCommand(
        note=args.note,
        deadline=args.deadline,
        supplier_ids=list(dict.fromkeys(args.supplier_ids)),
        lines=[
            QuoteRequestLineInput(
                bought_item_id=line.bought_item_id,
                source_item_id=line.source_item_id,
                project_id=line.project_id,
                quantity=line.quantity,
                unit=line.unit,
                demands=[
                    QuoteRequestLineDemandInput(
                        family=s.family, demand_item_id=s.demand_id, quantity=s.quantity
                    )
                    for s in line.shares
                ],
            )
            for line in lines
        ],
    )
    # One use case call writes the request, its suppliers and its lines in
    # one transaction, so a refusal leaves nothing behind.
    request = await (await ctx.use_case(get_create_quote_request_use_case)).execute(ctx.actor, cmd)
    return ToolOutput(
        {
            "quote_request": {
                "public_id": str(request.public_id),
                "request_number": request.request_number,
                "status": request.status,
                "suppliers": [s.supplier_name for s in request.suppliers],
                "lines": [
                    {
                        "item": line.item_name,
                        "quantity": line.quantity,
                        "unit": line.unit,
                    }
                    for line in request.lines
                ],
            },
            "next_step": (
                "A person reviews this draft quote request in Glados and sends it to the "
                "suppliers there. Nothing was sent."
            ),
        },
        created_refs=[ref("quote_request", request.public_id)],
    )


# ── draft_production_lot ──────────────────────────────────────────────


class DraftProductionLotInput(DraftToolInput):
    made_demand_ids: list[int] = Field(
        min_length=1,
        max_length=_MAX_DEMANDS,
        description=(
            "Made item demands the lot covers, all of one made item and one project; draft "
            f"one lot per made item and project. {_DEMAND_IDS_HINT}"
        ),
    )
    quantity: float | None = Field(
        default=None,
        gt=0,
        description=(
            "The pieces the lot makes. Leave it out to make exactly what the demands still "
            "lack; a larger number makes spare pieces."
        ),
    )
    note: str | None = Field(
        default=None, max_length=2000, description="An optional note on the lot."
    )

    @model_validator(mode="after")
    def _demands_once_each(self) -> Self:
        if len(self.made_demand_ids) != len(set(self.made_demand_ids)):
            raise ValueError("Name each demand once.")
        return self


async def _draft_production_lot(ctx: AgentToolContext, args: DraftProductionLotInput) -> ToolOutput:
    reader = await ctx.use_case(get_made_item_demand_use_case)
    summaries = await ctx.use_case(get_made_item_demand_summary_use_case)
    allocations: list[LotDemandAllocationInput] = []
    groups: set[tuple[int, int]] = set()
    desired: date | None = None
    for demand_id in args.made_demand_ids:
        demand = await reader.execute(demand_id=demand_id)
        MadeItemAllocationRules.assert_not_terminal(demand)
        share = _assert_lacks_pieces(
            "Made item demand",
            demand_id,
            (await summaries.execute(demand_item_id=demand_id)).unallocated,
        )
        groups.add((demand.made_item_id, demand.project_id))
        desired = _earlier(desired, demand.desired_delivery_date)
        allocations.append(LotDemandAllocationInput(demand_item_id=demand_id, quantity=share))
    if len(groups) != 1:
        raise InvalidInputError(
            "A lot makes one made item for one project; these demands span several. Draft one "
            "lot per made item and project."
        )
    [(made_item_id, project_id)] = groups

    # One use case call writes the lot, its positions and its demand links in
    # one transaction, so a refusal leaves nothing behind. The priority is
    # left to the use case, which takes it from the demands as the web app's
    # panel does.
    lot = await (await ctx.use_case(get_create_lot_use_case)).execute(
        actor=ctx.actor,
        cmd=CreateLotCommand(
            made_item_id=made_item_id,
            project_id=project_id,
            quantity=args.quantity or round(sum(a.quantity for a in allocations), 6),
            note=args.note,
            demand_allocations=allocations,
            required_delivery_date=desired,
        ),
    )
    data: dict[str, object] = {
        "lot": {
            "public_id": str(lot.public_id),
            "lot_number": lot.lot_number,
            "status": lot.status,
            "quantity": lot.quantity,
            "made_item_id": made_item_id,
            "project_id": project_id,
            "demand_ids": [a.demand_item_id for a in allocations],
        },
        "next_step": (
            "A person reviews this lot in Glados, assigns its positions and plans it there."
        ),
    }
    if lot.status != LotStatus.DRAFT:
        data["note"] = (
            f"The lot reads {lot.status}, not draft, because Glados queued the inspection "
            "orders of its inspection steps on creation, as for a lot created in the web app."
        )
    return ToolOutput(data, created_refs=[ref("lot", lot.public_id)])


# ── The tools ─────────────────────────────────────────────────────────

DRAFT_TOOLS: tuple[AgentTool, ...] = (
    AgentTool(
        name="draft_purchase_order",
        title="Draft a purchase order",
        description=(
            "Creates a DRAFT purchase order for one supplier with lines for open bought item "
            "and source item demands. Each demand gets the share it still lacks, and demands "
            "of one item, unit and project share one line. The order stays a draft: a person "
            "reviews it in Glados and places it there; nothing is ordered or sent to the "
            "supplier. Each line is added on its own, so if one is refused the result says "
            "so and lists the draft with the lines that were added."
        ),
        input_model=DraftPurchaseOrderInput,
        handler=_draft_purchase_order,
        kind=ToolKind.DRAFT,
        requires=(Permission.WRITE_ORDERS,),
    ),
    AgentTool(
        name="draft_quote_request",
        title="Draft a quote request",
        description=(
            "Creates a DRAFT quote request that asks the given suppliers for an offer on open "
            "bought item and source item demands, one line per item, unit and project. A "
            "demand share reserves nothing. The request stays a draft: a person reviews it in "
            "Glados and sends it to the suppliers there; nothing is sent."
        ),
        input_model=DraftQuoteRequestInput,
        handler=_draft_quote_request,
        kind=ToolKind.DRAFT,
        requires=(Permission.WRITE_ORDERS,),
    ),
    AgentTool(
        name="draft_production_lot",
        title="Draft a production lot",
        description=(
            "Creates a DRAFT production lot for open made item demands of one made item and "
            "one project, built from the made item's routing and linked to the demands. The "
            "lot waits for a person: they review it in Glados, assign its positions and plan "
            "it there. As for a lot created in the web app, inspection steps of the routing "
            "queue their inspection orders right away, and the result then names the status."
        ),
        input_model=DraftProductionLotInput,
        handler=_draft_production_lot,
        kind=ToolKind.DRAFT,
        requires=(Permission.WRITE_LOTS,),
    ),
)
