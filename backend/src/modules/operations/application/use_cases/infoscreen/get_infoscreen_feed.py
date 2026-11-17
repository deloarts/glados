"""
The two ways to read an infoscreen feed. The builder preview reads any
screen with a normal web session, open to every signed-in user like the
screens list. A device reads the screen assigned to it, and only once it is
approved. Both build the feed through the read tier's feed builder, so they answer
the same. Each adds the newest active message to terminals it would show: the
device the one reaching it, the preview one that goes to every terminal or
picks the screen.
"""

from src.modules.operations.application.dto.infoscreen_feed_dto import InfoscreenFeedResult
from src.modules.operations.application.mappers.terminal_mapper import broadcast_message
from src.modules.operations.application.services.infoscreen_feed_builder import (
    IInfoscreenFeedBuilder,
)
from src.modules.operations.domain.entities.terminal import Terminal
from src.modules.operations.domain.entities.terminal_broadcast import TerminalBroadcast
from src.modules.operations.domain.errors import InfoscreenNotFoundError
from src.modules.operations.domain.errors import TerminalNotReadyError
from src.modules.operations.domain.services import terminal_broadcast_rules
from src.modules.operations.domain.value_objects.terminal import TerminalStatus
from src.modules.operations.ports.outbound.repositories.infoscreen_repository import (
    IInfoscreenRepository,
)
from src.modules.operations.ports.outbound.repositories.terminal_broadcast_repository import (
    ITerminalBroadcastRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.shared_kernel.domain.services.clock import now_utc


def _with_broadcast(
    feed: InfoscreenFeedResult, broadcast: TerminalBroadcast | None
) -> InfoscreenFeedResult:
    if broadcast is None:
        return feed
    return feed.model_copy(update={"broadcast": broadcast_message(broadcast)})


class GetInfoscreenFeed:
    def __init__(
        self,
        infoscreen_repo: IInfoscreenRepository,
        builder: IInfoscreenFeedBuilder,
        broadcast_repo: ITerminalBroadcastRepository,
    ) -> None:
        self._screens = infoscreen_repo
        self._builder = builder
        self._broadcasts = broadcast_repo

    async def execute(self, infoscreen_id: int) -> InfoscreenFeedResult:
        screen = found_or_raise(
            await self._screens.get_by_id(infoscreen_id),
            InfoscreenNotFoundError,
            f"Infoscreen #{infoscreen_id} not found.",
        )
        feed = await self._builder.execute(screen)
        now = now_utc()
        return _with_broadcast(
            feed,
            terminal_broadcast_rules.newest_for_infoscreen(
                await self._broadcasts.get_active(now), screen.id, now
            ),
        )


class GetTerminalFeed:
    def __init__(
        self,
        infoscreen_repo: IInfoscreenRepository,
        builder: IInfoscreenFeedBuilder,
        broadcast_repo: ITerminalBroadcastRepository,
    ) -> None:
        self._screens = infoscreen_repo
        self._builder = builder
        self._broadcasts = broadcast_repo

    async def execute(self, terminal: Terminal) -> InfoscreenFeedResult:
        if terminal.status != TerminalStatus.APPROVED.value:
            raise TerminalNotReadyError(f"Terminal #{terminal.id} is not approved.")
        if terminal.infoscreen_id is None:
            raise TerminalNotReadyError(f"Terminal #{terminal.id} has no infoscreen assigned.")
        screen = await self._screens.get_by_id(terminal.infoscreen_id)
        if screen is None:
            raise TerminalNotReadyError(f"Terminal #{terminal.id} has no infoscreen assigned.")
        feed = await self._builder.execute(screen)
        now = now_utc()
        return _with_broadcast(
            feed,
            terminal_broadcast_rules.newest_for_terminal(
                await self._broadcasts.get_active(now), terminal, now
            ),
        )
