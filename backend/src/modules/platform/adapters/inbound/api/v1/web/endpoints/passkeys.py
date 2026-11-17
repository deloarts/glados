"""
Self-service management of the acting user's passkeys. Mounted at
/api/v1/web/users/me/passkeys. Always scoped to the acting user's own
passkeys; another user's are under /users/{user_id}/passkeys.
"""

from uuid import UUID

from fastapi import Depends
from fastapi import Request
from fastapi import Response
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.passkeys import (
    get_begin_passkey_registration_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.passkeys import (
    get_delete_all_my_passkeys_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.passkeys import get_delete_my_passkey_use_case
from src.modules.platform.adapters.inbound.api.deps.passkeys import (
    get_finish_passkey_registration_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.passkeys import get_my_passkeys_use_case
from src.modules.platform.adapters.inbound.api.deps.passkeys import get_rename_my_passkey_use_case
from src.modules.platform.adapters.inbound.api.schemas.passkey_schema import PasskeyChallenge
from src.modules.platform.adapters.inbound.api.schemas.passkey_schema import PasskeyRegisterRequest
from src.modules.platform.adapters.inbound.api.schemas.passkey_schema import (
    PasskeyRegistrationOptionsRequest,
)
from src.modules.platform.adapters.inbound.api.schemas.passkey_schema import PasskeyRenameRequest
from src.modules.platform.adapters.inbound.api.schemas.passkey_schema import PasskeyResult
from src.modules.platform.adapters.inbound.api.schemas.session_schema import RevokedCountResult
from src.modules.platform.adapters.inbound.api.v1.auth.login_responses import client_ip
from src.modules.platform.application.dto.passkey_dto import RegisterPasskeyCommand
from src.modules.platform.application.use_cases.passkey.manage_passkeys import DeleteAllMyPasskeys
from src.modules.platform.application.use_cases.passkey.manage_passkeys import DeleteMyPasskey
from src.modules.platform.application.use_cases.passkey.manage_passkeys import GetMyPasskeys
from src.modules.platform.application.use_cases.passkey.manage_passkeys import RenameMyPasskey
from src.modules.platform.application.use_cases.passkey.register_passkey import (
    BeginPasskeyRegistration,
)
from src.modules.platform.application.use_cases.passkey.register_passkey import (
    FinishPasskeyRegistration,
)
from src.modules.platform.domain.entities.user import User

router = APIRouter()


# Deliberately unpaginated: bounded per-user collection.
@router.get("/", response_model=list[PasskeyResult])
async def read_my_passkeys(
    actor: User = Depends(get_current_active_user),
    use_case: GetMyPasskeys = Depends(get_my_passkeys_use_case),
) -> list[PasskeyResult]:
    """The acting user's passkeys, newest first."""
    return await use_case.execute(actor)


@router.post("/registration-options", response_model=PasskeyChallenge)
async def passkey_registration_options(
    body: PasskeyRegistrationOptionsRequest,
    request: Request,
    actor: User = Depends(get_current_active_user),
    use_case: BeginPasskeyRegistration = Depends(get_begin_passkey_registration_use_case),
) -> PasskeyChallenge:
    """Confirm the current password and get the options for
    navigator.credentials.create(). A wrong password answers 400
    PasswordConfirmationFailedError and counts toward the login throttle."""
    return await use_case.execute(actor, body.password, client_ip=client_ip(request))


@router.post("/", response_model=PasskeyResult, status_code=status.HTTP_201_CREATED)
async def register_passkey(
    body: PasskeyRegisterRequest,
    actor: User = Depends(get_current_active_user),
    use_case: FinishPasskeyRegistration = Depends(get_finish_passkey_registration_use_case),
) -> PasskeyResult:
    """Verify the browser's registration response and store the passkey.
    Answers 400 PasskeyRegistrationFailedError when it does not verify or
    the challenge expired."""
    cmd = RegisterPasskeyCommand(
        challenge_token=body.challenge_token, credential=body.credential, name=body.name
    )
    return await use_case.execute(actor, cmd)


@router.delete("/", response_model=RevokedCountResult)
async def delete_all_my_passkeys(
    actor: User = Depends(get_current_active_user),
    use_case: DeleteAllMyPasskeys = Depends(get_delete_all_my_passkeys_use_case),
) -> RevokedCountResult:
    """Remove every passkey of the acting user; every device asks for the
    password again."""
    return RevokedCountResult(revoked=await use_case.execute(actor))


@router.patch("/{public_id}", response_model=PasskeyResult)
async def rename_my_passkey(
    public_id: UUID,
    body: PasskeyRenameRequest,
    actor: User = Depends(get_current_active_user),
    use_case: RenameMyPasskey = Depends(get_rename_my_passkey_use_case),
) -> PasskeyResult:
    """Give one of the acting user's passkeys a new name."""
    return await use_case.execute(actor, public_id, body.name)


@router.delete("/{public_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_passkey(
    public_id: UUID,
    actor: User = Depends(get_current_active_user),
    use_case: DeleteMyPasskey = Depends(get_delete_my_passkey_use_case),
) -> Response:
    await use_case.execute(actor, public_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
