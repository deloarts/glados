"""
What Catalogue offers agents: a made or bought item looked up by its part
number, with a made item's revisions and processes, and searches over the
source items (raw materials) and the suppliers.
"""

from pydantic import Field

from src.modules.catalogue.adapters.inbound.api.deps.catalogue import get_suppliers_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_bought_item_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_made_item_revisions_by_part_number_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.items import get_made_item_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_source_items_use_case
from src.modules.catalogue.domain.errors import BoughtItemNotFoundError
from src.modules.catalogue.domain.errors import MadeItemNotFoundError
from src.modules.catalogue.ports.outbound.catalogue_queries import SupplierFilterDto
from src.modules.catalogue.ports.outbound.repositories.source_item_repository import (
    SourceItemFilterDto,
)
from src.modules.platform.adapters.inbound.mcp.tools import AgentCatalog
from src.modules.platform.adapters.inbound.mcp.tools import AgentTool
from src.modules.platform.adapters.inbound.mcp.tools import AgentToolContext
from src.modules.platform.adapters.inbound.mcp.tools import ToolInput
from src.modules.platform.adapters.inbound.mcp.tools import ToolOutput

# ── item ──────────────────────────────────────────────────────────────


class ItemInput(ToolInput):
    part_number: str = Field(
        min_length=1,
        max_length=200,
        description="The part number of a made or bought item, exactly as Glados shows it.",
    )
    revision: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
        description=(
            "A made item's revision, such as 'B'. Leave it out to get the newest revision. "
            "Bought items have no revisions and ignore it."
        ),
    )


async def _item(ctx: AgentToolContext, args: ItemInput) -> ToolOutput:
    made_use_case = await ctx.use_case(get_made_item_use_case)
    try:
        made = await made_use_case.execute(part_number=args.part_number, revision=args.revision)
    except MadeItemNotFoundError:
        made = None
    if made is not None:
        revisions_use_case = await ctx.use_case(get_made_item_revisions_by_part_number_use_case)
        revisions = await revisions_use_case.execute(actor=ctx.actor, part_number=args.part_number)
        return ToolOutput(
            {
                "kind": "made",
                "item": made,
                "revisions": revisions.items,
            }
        )

    bought_use_case = await ctx.use_case(get_bought_item_use_case)
    try:
        bought = await bought_use_case.execute(part_number=args.part_number)
    except BoughtItemNotFoundError as e:
        raise BoughtItemNotFoundError(
            f"No made or bought item has the part number {args.part_number!r}."
        ) from e
    return ToolOutput({"kind": "bought", "item": bought})


# ── source_items ──────────────────────────────────────────────────────


class SourceItemsInput(ToolInput):
    search: str = Field(
        min_length=1,
        max_length=200,
        description=(
            "Text to find in a source item's type, dimension, material, note or order codes, "
            "such as 'S235' or '40x20'."
        ),
    )
    include_archived: bool = Field(default=False, description="Also list archived source items.")
    limit: int = Field(default=20, ge=1, le=100, description="The most source items to return.")


async def _source_items(ctx: AgentToolContext, args: SourceItemsInput) -> ToolOutput:
    use_case = await ctx.use_case(get_source_items_use_case)
    result = await use_case.execute(
        SourceItemFilterDto(
            search=args.search, include_archived=args.include_archived, limit=args.limit
        )
    )
    return ToolOutput({"total": result.total, "items": result.items[: args.limit]})


# ── suppliers ─────────────────────────────────────────────────────────


class SuppliersInput(ToolInput):
    search: str = Field(
        min_length=1,
        max_length=200,
        description="Text to find in a supplier's name, legal name or VAT id.",
    )
    include_archived: bool = Field(default=False, description="Also list archived suppliers.")
    limit: int = Field(default=20, ge=1, le=100, description="The most suppliers to return.")


async def _suppliers(ctx: AgentToolContext, args: SuppliersInput) -> ToolOutput:
    use_case = await ctx.use_case(get_suppliers_use_case)
    result = await use_case.execute(
        SupplierFilterDto(
            search=args.search, include_archived=args.include_archived, limit=args.limit
        )
    )
    return ToolOutput({"total": result.total, "items": result.items[: args.limit]})


CATALOGUE_AGENT_CATALOG = AgentCatalog(
    tools=(
        AgentTool(
            name="item",
            title="Catalogue item",
            description=(
                "Looks up a made or bought catalogue item by its part number. A made item comes "
                "with its routing (processes in order, with fabrication or inspection method and "
                "estimated minutes), its raw material and the list of all its revisions, newest "
                "first. A bought item comes with its manufacturer, order codes and status. Use it "
                "whenever a part number appears and you need to know what the part is."
            ),
            input_model=ItemInput,
            handler=_item,
        ),
        AgentTool(
            name="source_items",
            title="Source items",
            description=(
                "Searches the source items, the raw materials made items are cut from, such as "
                "a steel bar of a given dimension. Source items have no part number, so find them "
                "by material, dimension, type or order code."
            ),
            input_model=SourceItemsInput,
            handler=_source_items,
        ),
        AgentTool(
            name="suppliers",
            title="Suppliers",
            description=(
                "Searches the suppliers and manufacturers by name, legal name or VAT id, with "
                "their level, capabilities (fabrication methods) and article groups. Use it to "
                "find who can make or deliver something, or to resolve a manufacturer id."
            ),
            input_model=SuppliersInput,
            handler=_suppliers,
        ),
    ),
)
