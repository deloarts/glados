"""The device dependency of the terminal endpoints: resolves the terminal
behind `Authorization: Bearer <terminal token>`.

It reads only the header, never the session cookie, and only a terminal
token passes, since those are signed with a key of their own. A web session
token is therefore refused here, and a terminal token is refused by every
web, PAT and key dependency. The client address is `request.client.host`,
as for the maintenance allowlist. The server resolves it from
X-Forwarded-For only for a peer in NETWORK__TRUSTED_PROXIES (gunicorn_conf.py),
so a client cannot choose it.
"""

from fastapi import Depends
from fastapi import Request

from src.modules.operations.adapters.inbound.api.deps.repositories import (
    get_operations_settings_repo,
)
from src.modules.operations.adapters.inbound.api.deps.repositories import get_terminal_repo
from src.modules.operations.application.use_cases.terminal_device.authenticate_terminal import (
    AuthenticateTerminal,
)
from src.modules.operations.domain.entities.terminal import Terminal
from src.modules.operations.ports.outbound.operations_settings_repository import (
    IOperationsSettingsRepository,
)
from src.modules.operations.ports.outbound.repositories.terminal_repository import (
    ITerminalRepository,
)
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork

_BEARER = "Bearer "


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    return header[len(_BEARER) :].strip() if header.startswith(_BEARER) else ""


async def get_current_terminal(
    request: Request,
    terminal_repo: ITerminalRepository = Depends(get_terminal_repo),
    settings_repo: IOperationsSettingsRepository = Depends(get_operations_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> Terminal:
    """Raises the domain errors of AuthenticateTerminal, which answer 401,
    403 or 503 with their code."""
    return await AuthenticateTerminal(
        terminal_repo=terminal_repo, settings_repo=settings_repo, uow=uow
    ).execute(_bearer_token(request), client_ip(request))
