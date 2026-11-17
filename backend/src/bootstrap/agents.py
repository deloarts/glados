"""
Collects what every module offers AI agents and builds the MCP surface the
app mounts at API_MCP. Only the composition root may name every module, so
the list of catalogues lives here.
"""

from starlette.types import ASGIApp

from src.modules.catalogue.adapters.inbound.mcp.catalog import CATALOGUE_AGENT_CATALOG
from src.modules.external_data.adapters.inbound.mcp.catalog import EXTERNAL_DATA_AGENT_CATALOG
from src.modules.fulfillment.adapters.inbound.mcp.catalog import FULFILLMENT_AGENT_CATALOG
from src.modules.platform.adapters.inbound.mcp.catalog import PLATFORM_AGENT_CATALOG
from src.modules.platform.adapters.inbound.mcp.server import create_agent_app
from src.modules.platform.adapters.inbound.mcp.tools import AgentCatalog
from src.modules.platform.const import VERSION
from src.modules.quality.adapters.inbound.mcp.catalog import QUALITY_AGENT_CATALOG
from src.modules.workspace.adapters.inbound.mcp.catalog import WORKSPACE_AGENT_CATALOG
from src.read.adapters.inbound.mcp.catalog import READ_TIER_AGENT_CATALOG

AGENT_CATALOGS: tuple[AgentCatalog, ...] = (
    PLATFORM_AGENT_CATALOG,
    CATALOGUE_AGENT_CATALOG,
    WORKSPACE_AGENT_CATALOG,
    EXTERNAL_DATA_AGENT_CATALOG,
    FULFILLMENT_AGENT_CATALOG,
    QUALITY_AGENT_CATALOG,
    READ_TIER_AGENT_CATALOG,
)


def build_agent_app() -> ASGIApp:
    return create_agent_app(AGENT_CATALOGS, version=VERSION)
