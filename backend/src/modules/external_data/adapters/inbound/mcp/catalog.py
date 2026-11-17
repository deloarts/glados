"""
What CAD & external data offers agents: parts of the EPLAN Data Portal,
found by number or by text. The PDM admin views are not offered, because
they need read:settings, which no token may carry.
"""

from typing import Literal

from pydantic import Field

from src.modules.external_data.adapters.inbound.api.deps.items import get_match_edp_parts_use_case
from src.modules.external_data.adapters.inbound.api.deps.items import get_search_edp_parts_use_case
from src.modules.platform.adapters.inbound.mcp.tools import AgentCatalog
from src.modules.platform.adapters.inbound.mcp.tools import AgentTool
from src.modules.platform.adapters.inbound.mcp.tools import AgentToolContext
from src.modules.platform.adapters.inbound.mcp.tools import ToolInput
from src.modules.platform.adapters.inbound.mcp.tools import ToolOutput
from src.modules.platform.domain.value_objects.permission import Permission

# Each search spends the organisation's Data Portal token, so an agent gets
# fewer hits per call than the create dialog's search allows.
EDP_MAX_HITS = 10


# ── edp_lookup ────────────────────────────────────────────────────────


class EdpLookupInput(ToolInput):
    query: str = Field(
        min_length=2,
        max_length=100,
        description=(
            "With mode 'match', an order number, type number or EPLAN part number. With mode "
            "'search', a number or words of a part's name, such as 'DSNU-25' or 'round cylinder'."
        ),
    )
    mode: Literal["match", "search"] = Field(
        default="match",
        description=(
            "'match' returns only the parts the number names exactly. 'search' returns the "
            "portal's ranked hits for a number or a name. Prefer 'match' when you have a number."
        ),
    )
    manufacturer_id: int | None = Field(
        default=None,
        description=(
            "Only with mode 'match': the Glados id of the manufacturer, which narrows several "
            "makers sharing the number to that one. Find it with the suppliers tool."
        ),
    )
    limit: int = Field(
        default=5, ge=1, le=EDP_MAX_HITS, description="The most portal parts to return."
    )


async def _edp_lookup(ctx: AgentToolContext, args: EdpLookupInput) -> ToolOutput:
    if args.mode == "match":
        match_use_case = await ctx.use_case(get_match_edp_parts_use_case)
        result = await match_use_case.execute(
            actor=ctx.actor, number=args.query, manufacturer_id=args.manufacturer_id
        )
    else:
        search_use_case = await ctx.use_case(get_search_edp_parts_use_case)
        result = await search_use_case.execute(actor=ctx.actor, query=args.query, limit=args.limit)
    return ToolOutput({"hits": result.hits[: args.limit]})


EXTERNAL_DATA_AGENT_CATALOG = AgentCatalog(
    tools=(
        AgentTool(
            name="edp_lookup",
            title="EPLAN Data Portal lookup",
            description=(
                "Looks a part up in the EPLAN Data Portal, the external catalogue of "
                "manufacturer parts. Each hit carries the portal part, the bought-item values it "
                "would fill (article name, order codes, EAN, manufacturer, product family) and "
                "the Glados bought item that already describes it, if any. It calls an external "
                "service, so ask for few hits and do not repeat a call that answered. Fails when "
                "the Data Portal is switched off."
            ),
            input_model=EdpLookupInput,
            handler=_edp_lookup,
            requires=(Permission.USE_DATA_PORTAL,),
        ),
    ),
)
