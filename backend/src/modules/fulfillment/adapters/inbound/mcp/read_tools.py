"""
The read tools of Planning and fulfillment. Each one builds the use case of
the web route it mirrors and changes nothing.
"""

from src.modules.fulfillment.adapters.inbound.mcp.read_tools_lots import EXPLAIN_LOT
from src.modules.fulfillment.adapters.inbound.mcp.read_tools_planning import (
    LIST_PLANNING_EXCEPTIONS,
)
from src.modules.fulfillment.adapters.inbound.mcp.read_tools_planning import MY_BRIEFING
from src.modules.fulfillment.adapters.inbound.mcp.read_tools_planning import SCHEDULE
from src.modules.fulfillment.adapters.inbound.mcp.read_tools_planning import SHOP_FLOOR_NOW
from src.modules.fulfillment.adapters.inbound.mcp.read_tools_supply import COMPARE_OFFERS
from src.modules.fulfillment.adapters.inbound.mcp.read_tools_supply import DEMAND_COVERAGE
from src.modules.fulfillment.adapters.inbound.mcp.read_tools_supply import ORDERS
from src.modules.platform.adapters.inbound.mcp.tools import AgentResource
from src.modules.platform.adapters.inbound.mcp.tools import AgentTool

READ_TOOLS: tuple[AgentTool, ...] = (
    MY_BRIEFING,
    LIST_PLANNING_EXCEPTIONS,
    EXPLAIN_LOT,
    DEMAND_COVERAGE,
    SCHEDULE,
    SHOP_FLOOR_NOW,
    ORDERS,
    COMPARE_OFFERS,
)

READ_RESOURCES: tuple[AgentResource, ...] = (
    AgentResource(
        uri_template="glados://lot/{number}",
        name="lot",
        title="Production lot",
        description=(
            "One production lot by its lot number, with its positions, demands, planning "
            "exceptions and latest timeline events, as explain_lot returns it."
        ),
        tool=EXPLAIN_LOT.name,
        argument="number",
    ),
)
