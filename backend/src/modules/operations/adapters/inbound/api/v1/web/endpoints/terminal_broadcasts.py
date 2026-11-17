"""
Messages to terminals. Prefix `/terminal-broadcasts`. Listing the active
messages and counting the reach of a draft audience are open to every
signed-in user; sending and ending need manage:terminals, checked in the use
case. The displays receive a message through their device state, never with
its author.
"""

from fastapi import Depends
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.operations.adapters.inbound.api.deps.terminals import (
    get_count_terminal_broadcast_reach_use_case,
)
from src.modules.operations.adapters.inbound.api.deps.terminals import (
    get_end_terminal_broadcast_use_case,
)
from src.modules.operations.adapters.inbound.api.deps.terminals import (
    get_list_active_terminal_broadcasts_use_case,
)
from src.modules.operations.adapters.inbound.api.deps.terminals import (
    get_send_terminal_broadcast_use_case,
)
from src.modules.operations.adapters.inbound.api.schemas.terminal_schema import (
    TerminalBroadcastAudienceRequest,
)
from src.modules.operations.adapters.inbound.api.schemas.terminal_schema import (
    TerminalBroadcastCreateRequest,
)
from src.modules.operations.adapters.inbound.api.schemas.terminal_schema import (
    TerminalBroadcastReachResponse,
)
from src.modules.operations.adapters.inbound.api.schemas.terminal_schema import (
    TerminalBroadcastResponse,
)
from src.modules.operations.application.dto.terminal_broadcast_dto import (
    SendTerminalBroadcastCommand,
)
from src.modules.operations.application.dto.terminal_broadcast_dto import (
    TerminalBroadcastAudienceCommand,
)
from src.modules.operations.application.dto.terminal_broadcast_dto import (
    TerminalBroadcastReachResult,
)
from src.modules.operations.application.dto.terminal_broadcast_dto import TerminalBroadcastResult
from src.modules.operations.application.use_cases.terminal.terminal_broadcasts import (
    CountTerminalBroadcastReach,
)
from src.modules.operations.application.use_cases.terminal.terminal_broadcasts import (
    EndTerminalBroadcast,
)
from src.modules.operations.application.use_cases.terminal.terminal_broadcasts import (
    ListActiveTerminalBroadcasts,
)
from src.modules.operations.application.use_cases.terminal.terminal_broadcasts import (
    SendTerminalBroadcast,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/", response_model=list[TerminalBroadcastResponse])
async def read_active_terminal_broadcasts(
    _: User = Depends(get_current_active_user),
    use_case: ListActiveTerminalBroadcasts = Depends(get_list_active_terminal_broadcasts_use_case),
) -> list[TerminalBroadcastResult]:
    """The messages shown right now, newest first, each with how many
    approved terminals it reaches."""
    return await use_case.execute()


@router.post("/", response_model=TerminalBroadcastResponse, status_code=status.HTTP_201_CREATED)
async def send_terminal_broadcast(
    body: TerminalBroadcastCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: SendTerminalBroadcast = Depends(get_send_terminal_broadcast_use_case),
) -> TerminalBroadcastResult:
    return await use_case.execute(actor, SendTerminalBroadcastCommand(**body.model_dump()))


@router.post("/reach", response_model=TerminalBroadcastReachResponse)
async def count_terminal_broadcast_reach(
    body: TerminalBroadcastAudienceRequest,
    _: User = Depends(get_current_active_user),
    use_case: CountTerminalBroadcastReach = Depends(get_count_terminal_broadcast_reach_use_case),
) -> TerminalBroadcastReachResult:
    """How many approved terminals the audience reaches now."""
    return await use_case.execute(TerminalBroadcastAudienceCommand(**body.model_dump()))


@router.post("/{broadcast_id}/end", response_model=TerminalBroadcastResponse)
async def end_terminal_broadcast(
    broadcast_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: EndTerminalBroadcast = Depends(get_end_terminal_broadcast_use_case),
) -> TerminalBroadcastResult:
    """Ends the message now; a message that already ended stays as it is."""
    return await use_case.execute(actor, broadcast_id)
