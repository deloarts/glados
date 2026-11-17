"""
Builds the state a device reads: its own terminal row, the power its display
should have now and when that changes, and the newest active message to
terminals that reaches it. The session call and the state endpoint both
answer with it.
"""

from src.modules.operations.application.dto.terminal_dto import TerminalDeviceStateResult
from src.modules.operations.application.mappers.terminal_mapper import TerminalMapper
from src.modules.operations.application.services.display_calendar import DisplayCalendarReader
from src.modules.operations.domain.entities.terminal import Terminal
from src.modules.operations.domain.services import display_power_rules
from src.modules.operations.domain.services import terminal_broadcast_rules
from src.modules.operations.ports.outbound.repositories.terminal_broadcast_repository import (
    ITerminalBroadcastRepository,
)
from src.shared_kernel.domain.services.clock import now_utc


class TerminalDeviceStateReader:
    def __init__(
        self, calendar: DisplayCalendarReader, broadcast_repo: ITerminalBroadcastRepository
    ) -> None:
        self._calendar = calendar
        self._broadcasts = broadcast_repo

    async def read(self, terminal: Terminal) -> TerminalDeviceStateResult:
        now = now_utc()
        power = display_power_rules.terminal_display_power(
            terminal, await self._calendar.read(now), now
        )
        broadcast = terminal_broadcast_rules.newest_for_terminal(
            await self._broadcasts.get_active(now), terminal, now
        )
        return TerminalMapper.to_device_state(terminal, power=power, broadcast=broadcast)
