"""
The state a signed-in device reads: its approval, its screen, the commands
waiting for it, its display power and the message it shows. The terminal is
the one get_current_terminal resolved for this request.
"""

from src.modules.operations.application.dto.terminal_dto import TerminalDeviceStateResult
from src.modules.operations.application.services.terminal_device_state import (
    TerminalDeviceStateReader,
)
from src.modules.operations.domain.entities.terminal import Terminal


class GetTerminalDeviceState:
    def __init__(self, state_reader: TerminalDeviceStateReader) -> None:
        self._state = state_reader

    async def execute(self, terminal: Terminal) -> TerminalDeviceStateResult:
        return await self._state.read(terminal)
