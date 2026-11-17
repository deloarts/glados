"""
Terminal admin endpoints. Prefix `/terminals`. Listing is open to every
signed-in user, who sees the identifying details (key fingerprint, client
addresses, serials, hostname) only with manage:terminals; every action needs
manage:terminals, checked in its use case. Pending terminals whose pairing
code expired are left out of the list.

The actions on all terminals live under `/all/...` and are declared before
the routes that take a terminal id, so `all` is never read as an id.
"""

from fastapi import Depends
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.operations.adapters.inbound.api.deps.terminals import get_approve_terminal_use_case
from src.modules.operations.adapters.inbound.api.deps.terminals import (
    get_clear_terminal_display_override_use_case,
)
from src.modules.operations.adapters.inbound.api.deps.terminals import (
    get_delete_all_terminals_use_case,
)
from src.modules.operations.adapters.inbound.api.deps.terminals import get_delete_terminal_use_case
from src.modules.operations.adapters.inbound.api.deps.terminals import (
    get_identify_all_terminals_use_case,
)
from src.modules.operations.adapters.inbound.api.deps.terminals import get_list_terminals_use_case
from src.modules.operations.adapters.inbound.api.deps.terminals import (
    get_reload_all_terminals_use_case,
)
from src.modules.operations.adapters.inbound.api.deps.terminals import (
    get_request_terminal_identify_use_case,
)
from src.modules.operations.adapters.inbound.api.deps.terminals import (
    get_request_terminal_reload_use_case,
)
from src.modules.operations.adapters.inbound.api.deps.terminals import (
    get_revoke_all_terminals_use_case,
)
from src.modules.operations.adapters.inbound.api.deps.terminals import get_revoke_terminal_use_case
from src.modules.operations.adapters.inbound.api.deps.terminals import (
    get_set_terminal_display_override_use_case,
)
from src.modules.operations.adapters.inbound.api.deps.terminals import get_update_terminal_use_case
from src.modules.operations.adapters.inbound.api.schemas.terminal_schema import (
    TerminalApproveRequest,
)
from src.modules.operations.adapters.inbound.api.schemas.terminal_schema import (
    TerminalBulkActionResponse,
)
from src.modules.operations.adapters.inbound.api.schemas.terminal_schema import (
    TerminalDisplayOverrideRequest,
)
from src.modules.operations.adapters.inbound.api.schemas.terminal_schema import TerminalResponse
from src.modules.operations.adapters.inbound.api.schemas.terminal_schema import (
    TerminalUpdateRequest,
)
from src.modules.operations.application.dto.terminal_dto import ApproveTerminalCommand
from src.modules.operations.application.dto.terminal_dto import SetDisplayOverrideCommand
from src.modules.operations.application.dto.terminal_dto import TerminalBulkResult
from src.modules.operations.application.dto.terminal_dto import TerminalResult
from src.modules.operations.application.dto.terminal_dto import UpdateTerminalCommand
from src.modules.operations.application.use_cases.terminal.terminal_admin import ApproveTerminal
from src.modules.operations.application.use_cases.terminal.terminal_admin import (
    ClearTerminalDisplayOverride,
)
from src.modules.operations.application.use_cases.terminal.terminal_admin import DeleteTerminal
from src.modules.operations.application.use_cases.terminal.terminal_admin import ListTerminals
from src.modules.operations.application.use_cases.terminal.terminal_admin import (
    RequestTerminalIdentify,
)
from src.modules.operations.application.use_cases.terminal.terminal_admin import (
    RequestTerminalReload,
)
from src.modules.operations.application.use_cases.terminal.terminal_admin import RevokeTerminal
from src.modules.operations.application.use_cases.terminal.terminal_admin import (
    SetTerminalDisplayOverride,
)
from src.modules.operations.application.use_cases.terminal.terminal_admin import UpdateTerminal
from src.modules.operations.application.use_cases.terminal.terminal_bulk import DeleteAllTerminals
from src.modules.operations.application.use_cases.terminal.terminal_bulk import IdentifyAllTerminals
from src.modules.operations.application.use_cases.terminal.terminal_bulk import ReloadAllTerminals
from src.modules.operations.application.use_cases.terminal.terminal_bulk import RevokeAllTerminals
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/", response_model=list[TerminalResponse])
async def read_terminals(
    actor: User = Depends(get_current_active_user),
    use_case: ListTerminals = Depends(get_list_terminals_use_case),
) -> list[TerminalResult]:
    """Without manage:terminals the fingerprint, both addresses and the
    device serials and hostname are null."""
    return await use_case.execute(actor)


# ── All terminals ─────────────────────────────────────────────────────


@router.post("/all/reload", response_model=TerminalBulkActionResponse)
async def reload_all_terminals(
    actor: User = Depends(get_current_active_user),
    use_case: ReloadAllTerminals = Depends(get_reload_all_terminals_use_case),
) -> TerminalBulkResult:
    """Every approved terminal reloads its page."""
    return await use_case.execute(actor)


@router.post("/all/identify", response_model=TerminalBulkActionResponse)
async def identify_all_terminals(
    actor: User = Depends(get_current_active_user),
    use_case: IdentifyAllTerminals = Depends(get_identify_all_terminals_use_case),
) -> TerminalBulkResult:
    """Every approved terminal shows its name and location for a moment."""
    return await use_case.execute(actor)


@router.post("/all/revoke", response_model=TerminalBulkActionResponse)
async def revoke_all_terminals(
    actor: User = Depends(get_current_active_user),
    use_case: RevokeAllTerminals = Depends(get_revoke_all_terminals_use_case),
) -> TerminalBulkResult:
    """Revokes every approved terminal."""
    return await use_case.execute(actor)


@router.post("/all/delete", response_model=TerminalBulkActionResponse)
async def delete_all_terminals(
    actor: User = Depends(get_current_active_user),
    use_case: DeleteAllTerminals = Depends(get_delete_all_terminals_use_case),
) -> TerminalBulkResult:
    """Deletes every terminal, waiting and revoked ones included."""
    return await use_case.execute(actor)


# ── One terminal ──────────────────────────────────────────────────────


@router.post("/{terminal_id}/approve", response_model=TerminalResponse)
async def approve_terminal(
    terminal_id: int,
    body: TerminalApproveRequest,
    actor: User = Depends(get_current_active_user),
    use_case: ApproveTerminal = Depends(get_approve_terminal_use_case),
) -> TerminalResult:
    """Approve with the pairing code the display shows; 422 when it does not
    match or has expired."""
    return await use_case.execute(actor, terminal_id, ApproveTerminalCommand(**body.model_dump()))


@router.patch("/{terminal_id}", response_model=TerminalResponse)
async def update_terminal(
    terminal_id: int,
    body: TerminalUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateTerminal = Depends(get_update_terminal_use_case),
) -> TerminalResult:
    cmd = UpdateTerminalCommand(**body.model_dump(), fields_set=set(body.model_fields_set))
    return await use_case.execute(actor, terminal_id, cmd)


@router.post("/{terminal_id}/revoke", response_model=TerminalResponse)
async def revoke_terminal(
    terminal_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: RevokeTerminal = Depends(get_revoke_terminal_use_case),
) -> TerminalResult:
    return await use_case.execute(actor, terminal_id)


@router.post("/{terminal_id}/reload", response_model=TerminalResponse)
async def reload_terminal(
    terminal_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: RequestTerminalReload = Depends(get_request_terminal_reload_use_case),
) -> TerminalResult:
    return await use_case.execute(actor, terminal_id)


@router.post("/{terminal_id}/identify", response_model=TerminalResponse)
async def identify_terminal(
    terminal_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: RequestTerminalIdentify = Depends(get_request_terminal_identify_use_case),
) -> TerminalResult:
    return await use_case.execute(actor, terminal_id)


@router.post("/{terminal_id}/display-override", response_model=TerminalResponse)
async def set_display_override(
    terminal_id: int,
    body: TerminalDisplayOverrideRequest,
    actor: User = Depends(get_current_active_user),
    use_case: SetTerminalDisplayOverride = Depends(get_set_terminal_display_override_use_case),
) -> TerminalResult:
    """Forces the display on or off until `until`, or until the next change
    of its screen's schedule. 409 for a terminal that is not approved."""
    return await use_case.execute(
        actor, terminal_id, SetDisplayOverrideCommand(**body.model_dump())
    )


@router.delete("/{terminal_id}/display-override", response_model=TerminalResponse)
async def clear_display_override(
    terminal_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: ClearTerminalDisplayOverride = Depends(get_clear_terminal_display_override_use_case),
) -> TerminalResult:
    """Hands the display back to its screen's schedule."""
    return await use_case.execute(actor, terminal_id)


@router.delete("/{terminal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_terminal(
    terminal_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: DeleteTerminal = Depends(get_delete_terminal_use_case),
) -> None:
    await use_case.execute(actor, terminal_id)
