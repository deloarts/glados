"""
Creates terminal keys, mounted under the admin API key path next to
api_keys.py: a terminal key is an API key whose only permission lets an
unknown display register itself, so it has no permission picker. The key is
Operations' business, while the key list and revocation stay with the API
keys.
"""

from fastapi import Depends
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.operations.adapters.inbound.api.deps.terminals import (
    get_create_terminal_key_use_case,
)
from src.modules.operations.adapters.inbound.api.schemas.terminal_schema import (
    TerminalKeyCreateRequest,
)
from src.modules.operations.application.dto.terminal_dto import CreateTerminalKeyCommand
from src.modules.operations.application.use_cases.terminal.create_terminal_key import (
    CreateTerminalKey,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.schemas.api_key_schema import CreatedApiKeyResult
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.post("/terminal", response_model=CreatedApiKeyResult, status_code=status.HTTP_201_CREATED)
async def create_terminal_key(
    body: TerminalKeyCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateTerminalKey = Depends(get_create_terminal_key_use_case),
) -> CreatedApiKeyResult:
    """A terminal key, shown once. Requires manage:api_keys."""
    return await use_case.execute(actor=actor, cmd=CreateTerminalKeyCommand(**body.model_dump()))
