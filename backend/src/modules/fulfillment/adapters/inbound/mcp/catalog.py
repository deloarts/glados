"""
What Planning and fulfillment offers AI agents: the read tools over demands,
orders, quote requests, lots and the schedule, and the draft tools that
prepare a purchase order, a quote request or a production lot for a person
to commit.
"""

from src.modules.fulfillment.adapters.inbound.mcp.draft_tools import DRAFT_TOOLS
from src.modules.fulfillment.adapters.inbound.mcp.read_tools import READ_RESOURCES
from src.modules.fulfillment.adapters.inbound.mcp.read_tools import READ_TOOLS
from src.modules.platform.adapters.inbound.mcp.tools import AgentCatalog

FULFILLMENT_AGENT_CATALOG = AgentCatalog(tools=READ_TOOLS + DRAFT_TOOLS, resources=READ_RESOURCES)
