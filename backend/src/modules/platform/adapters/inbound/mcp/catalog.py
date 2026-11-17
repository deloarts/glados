"""
What Platform offers agents: the caller's own in-app notifications.
"""

from pydantic import Field

from src.modules.platform.adapters.inbound.api.deps.admin import get_notifications_use_case
from src.modules.platform.adapters.inbound.mcp.tools import AgentCatalog
from src.modules.platform.adapters.inbound.mcp.tools import AgentTool
from src.modules.platform.adapters.inbound.mcp.tools import AgentToolContext
from src.modules.platform.adapters.inbound.mcp.tools import ToolInput
from src.modules.platform.adapters.inbound.mcp.tools import ToolOutput


class MyNotificationsInput(ToolInput):
    unread_only: bool = Field(default=True, description="Only the notifications not read yet.")
    limit: int = Field(default=25, ge=1, le=100, description="The most notifications to return.")


async def _my_notifications(ctx: AgentToolContext, args: MyNotificationsInput) -> ToolOutput:
    use_case = await ctx.use_case(get_notifications_use_case)
    result = await use_case.execute(ctx.actor, unread_only=args.unread_only)
    return ToolOutput(
        {
            "unread_count": result.unread_count,
            "total": result.total,
            "items": result.items[: args.limit],
        }
    )


PLATFORM_AGENT_CATALOG = AgentCatalog(
    tools=(
        AgentTool(
            name="my_notifications",
            title="My notifications",
            description=(
                "The in-app notifications of the person you act for, newest first: fulfilled or "
                "canceled demands, canceled orders, scrapped pieces, lots that ended short, "
                "document changes and assignments. Reading them does not mark them read."
            ),
            input_model=MyNotificationsInput,
            handler=_my_notifications,
        ),
    ),
)
