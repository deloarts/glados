"""
Small pieces the read tools of Planning and fulfillment share: the limit
argument, picking a few fields from a result, and the tenant's today.
"""

from datetime import date
from datetime import tzinfo
from typing import Any

from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.adapters.inbound.api.deps.misc import get_tenant_zone
from src.modules.platform.adapters.inbound.mcp.labels import resolved_labels
from src.modules.platform.adapters.inbound.mcp.tools import AgentToolContext
from src.shared_kernel.domain.services.clock import today_in

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


def limit_field(default: int = DEFAULT_LIMIT, what: str = "rows") -> Any:
    """The `limit` argument of a tool, capped so a result stays small."""
    return Field(
        default=default, ge=1, le=MAX_LIMIT, description=f"The most {what} to return per list."
    )


def pick(model: BaseModel, *fields: str) -> dict[str, Any]:
    """The named fields of a result, JSON shaped, in the model's order, with
    catalogue labels resolved (see platform/adapters/inbound/mcp/labels.py)."""
    return dict(resolved_labels(model.model_dump(mode="json", include=set(fields))))


async def tenant_today(ctx: AgentToolContext) -> tuple[date, tzinfo]:
    """Today in the tenant's timezone and the zone itself, read as the web
    routes read them."""
    # The resolver awaits a coroutine factory, which the signature of
    # use_case does not express, hence the cast.
    zone = await ctx.use_case(get_tenant_zone)
    return today_in(zone), zone
