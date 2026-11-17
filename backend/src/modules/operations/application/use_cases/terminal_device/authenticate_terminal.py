"""
Resolves the terminal behind a device request's access token. The terminal
is reloaded on every request, so a revoke, a deletion or a switched-off
terminal setting takes effect at once rather than when the token expires.
The terminal allowlist and maintenance mode apply to every device request.

A request also refreshes the stored last-seen time once it has grown stale,
committed right away like the session touch of ValidateWebToken, so a
display that only polls still shows up as alive on the terminals tab.
"""

from src.modules.operations.domain.entities.terminal import Terminal
from src.modules.operations.domain.errors import TerminalTokenInvalidError
from src.modules.operations.domain.services import terminal_rules
from src.modules.operations.domain.value_objects.terminal import TERMINAL_LAST_SEEN_TOUCH
from src.modules.operations.infrastructure.security.terminal_auth import terminal_id_from_token
from src.modules.operations.ports.outbound.operations_settings_repository import (
    IOperationsSettingsRepository,
)
from src.modules.operations.ports.outbound.repositories.terminal_repository import (
    ITerminalRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


class AuthenticateTerminal:
    def __init__(
        self,
        terminal_repo: ITerminalRepository,
        settings_repo: IOperationsSettingsRepository,
        uow: IUnitOfWork,
    ) -> None:
        self._terminals = terminal_repo
        self._settings = settings_repo
        self._uow = uow

    async def execute(self, token: str, client_ip: str | None) -> Terminal:
        terminal_id = terminal_id_from_token(token)
        if terminal_id is None:
            raise TerminalTokenInvalidError("Invalid or expired terminal token.")
        terminal_rules.assert_access_allowed(await self._settings.get_security(), client_ip)
        terminal_rules.assert_maintenance_allows_device(
            await self._settings.get_maintenance(), client_ip
        )
        terminal = await self._terminals.get_by_id(terminal_id)
        if terminal is None:
            raise TerminalTokenInvalidError("The terminal of this token no longer exists.")

        now = now_utc()
        if now - terminal.last_seen_at >= TERMINAL_LAST_SEEN_TOUCH or terminal.last_ip != client_ip:
            # Only the two telemetry columns: saving the whole terminal here
            # would write the status this request read back over a revoke
            # or approval an admin committed in the meantime.
            await self._terminals.touch_seen(terminal.id, now, client_ip)
            await self._uow.commit()
            terminal.last_seen_at = now
            terminal.last_ip = client_ip
        return terminal
