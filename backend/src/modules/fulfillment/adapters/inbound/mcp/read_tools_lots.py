"""
The lot read tool: one lot with everything that explains its state, found
by its lot number.
"""

from typing import Any

from pydantic import Field

from src.modules.fulfillment.adapters.inbound.api.deps.lots import get_lot_demands_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.lots import get_lot_events_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.lots import (
    get_lot_material_receipts_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.lots import (
    get_lot_position_balances_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.lots import get_lots_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_planning_exceptions_use_case,
)
from src.modules.fulfillment.adapters.inbound.mcp.read_tools_common import limit_field
from src.modules.fulfillment.adapters.inbound.mcp.read_tools_common import pick
from src.modules.fulfillment.application.dto.production_lot_dto import LotSummaryResult
from src.modules.fulfillment.domain.errors import LotNotFoundError
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.source_approval_status import SourceApprovalStatus
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    LotFilterDto,
)
from src.modules.platform.adapters.inbound.mcp.labels import resolved_labels
from src.modules.platform.adapters.inbound.mcp.tools import AgentTool
from src.modules.platform.adapters.inbound.mcp.tools import AgentToolContext
from src.modules.platform.adapters.inbound.mcp.tools import ToolInput
from src.modules.platform.adapters.inbound.mcp.tools import ToolOutput

# How many lots the number lookup reads, enough to name a few near misses.
_LOOKUP_LIMIT = 10

# The parts of the lot summary an agent does not need: the buttons of the
# web app, edit versions, and the lot's creator and last changer, which the
# event timeline already names.
_LOT_EXCLUDE: dict[str, Any] = {
    "actions": True,
    "blocked_actions": True,
    "creator": True,
    "changed_by": True,
    "edit_version": True,
    "steps": {"__all__": {"actions": True}},
    "positions": {
        "__all__": {
            "order_item_edit_version": True,
            "production_orders": {"__all__": {"edit_version": True}},
        }
    },
}

_DEMAND_FIELDS = (
    "id",
    "status",
    "project_number",
    "item_part_number",
    "item_revision",
    "item_article_name",
    "quantity",
    "allocated_quantity",
    "unit",
    "desired_delivery_date",
    "high_priority",
    "canceled_at",
    "fulfilled_manually_at",
)

_EVENT_FIELDS = (
    "occurred_at",
    "event_type",
    "entity",
    "entity_id",
    "summary",
    "actor_full_name",
    "payload",
)


class ExplainLotInput(ToolInput):
    number: str = Field(
        min_length=1, max_length=64, description="The lot number, such as the one on its label."
    )
    events_limit: int = limit_field(30, "timeline events, the latest ones")


async def find_lot(ctx: AgentToolContext, number: str) -> LotSummaryResult:
    """The lot with this number, read through the lot list's own filter. A
    number that matches no lot exactly names the near misses, if any."""
    use_case = await ctx.use_case(get_lots_use_case)
    _, lots = await use_case.execute(LotFilterDto(lot_number=number, limit=_LOOKUP_LIMIT))
    wanted = number.strip().casefold()
    for lot in lots:
        if lot.lot_number.casefold() == wanted:
            return lot
    if lots:
        similar = ", ".join(lot.lot_number for lot in lots)
        raise LotNotFoundError(f"No lot is numbered {number!r}. Similar numbers: {similar}.")
    raise LotNotFoundError(f"No lot is numbered {number!r}.")


def _hints(lot: LotSummaryResult) -> list[str]:
    """Plain statements about the lot's state that its fields alone do not
    make obvious to a reader."""
    hints: list[str] = []
    has_source = any(
        source is not None
        for source in (lot.source_bought_item_id, lot.source_item_id, lot.source_made_item_id)
    )
    if not has_source:
        hints.append(
            "The lot has no material source yet. A lot without a source stays unplanned until "
            "a source is selected and approved; this is by design, not a fault."
        )
    elif lot.source_approval_status == SourceApprovalStatus.PENDING:
        hints.append(
            "The lot's material source waits for approval by someone with manage:lots. Until "
            "then no raw material demand exists and the lot is not planned; this is by design."
        )
    elif lot.source_approval_status == SourceApprovalStatus.AWAITING_FIRST_STEP:
        hints.append(
            "The lot's first position is expected to go to a supplier, who brings the material, "
            "so the lot has no raw material demand. If the position is made in house instead, "
            "the lot demands its material then; this is by design."
        )
    elif lot.source_approval_status == SourceApprovalStatus.SUPPLIER_SOURCED:
        hints.append(
            "A supplier does the lot's first position and brings the material, so the lot has "
            "no raw material demand and nothing to approve; this is by design."
        )
    elif lot.source_approval_status == SourceApprovalStatus.REJECTED:
        reason = lot.source_rejection_reason or "no reason given"
        hints.append(
            f"The lot's material source was rejected ({reason}). It waits until the source is "
            "switched or approved again."
        )
    if lot.status == LotStatus.ON_HOLD:
        hints.append("The lot is on hold; the timeline names who held it and why.")
    return hints


async def _explain_lot(ctx: AgentToolContext, args: ExplainLotInput) -> ToolOutput:
    lot = await find_lot(ctx, args.number)

    events = await (await ctx.use_case(get_lot_events_use_case)).execute(lot_id=lot.id)
    demands = await (await ctx.use_case(get_lot_demands_use_case)).execute(lot_id=lot.id)
    balances = await (await ctx.use_case(get_lot_position_balances_use_case)).execute(lot_id=lot.id)
    receipts = await (await ctx.use_case(get_lot_material_receipts_use_case)).execute(lot_id=lot.id)
    exceptions = await (await ctx.use_case(get_planning_exceptions_use_case)).execute()

    latest = sorted(events, key=lambda e: e.occurred_at)[-args.events_limit :]
    return ToolOutput(
        {
            "lot": resolved_labels(lot.model_dump(mode="json", exclude=_LOT_EXCLUDE)),
            "hints": _hints(lot),
            "planning_exceptions": [e for e in exceptions if e.lot_id == lot.id],
            "demands": [pick(d, *_DEMAND_FIELDS) for d in demands],
            "position_balances": balances,
            "material_receipts": receipts[: args.events_limit],
            "events_total": len(events),
            "events": [pick(e, *_EVENT_FIELDS) for e in latest],
        }
    )


EXPLAIN_LOT = AgentTool(
    name="explain_lot",
    title="Explain a lot",
    description=(
        "Everything that explains one production lot, found by its lot number: its status, "
        "target date, material source and approval, positions with their production orders "
        "and supplier lines, the made demands it serves, where its pieces went, the raw "
        "material received for it, its planning exceptions and its latest timeline events. "
        "Use it to answer why a lot is late, unplanned, on hold or short. A lot without an "
        "approved material source waits for one by design."
    ),
    input_model=ExplainLotInput,
    handler=_explain_lot,
)
