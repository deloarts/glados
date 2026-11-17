"""
The passkey login: the options for the browser's prompt, then the signed
answer exchanged for a session. The login policy lives in PasskeyLogin.
Both routes are public; the first hands out nothing but a fresh challenge.
"""

from fastapi import Depends
from fastapi import Request
from fastapi import Response
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.deps.passkeys import get_begin_passkey_login_use_case
from src.modules.platform.adapters.inbound.api.deps.passkeys import get_passkey_login_use_case
from src.modules.platform.adapters.inbound.api.schemas.passkey_schema import PasskeyChallenge
from src.modules.platform.adapters.inbound.api.schemas.passkey_schema import PasskeyLoginRequest
from src.modules.platform.adapters.inbound.api.schemas.token_schema import TokenResponse
from src.modules.platform.adapters.inbound.api.v1.auth.login_responses import client_ip
from src.modules.platform.adapters.inbound.api.v1.auth.login_responses import session_response
from src.modules.platform.application.dto.passkey_dto import PasskeyLoginCommand
from src.modules.platform.application.use_cases.auth.passkey_login import BeginPasskeyLogin
from src.modules.platform.application.use_cases.auth.passkey_login import PasskeyLogin

router = APIRouter()


@router.post("/login/passkey/options", response_model=PasskeyChallenge)
async def passkey_login_options(
    use_case: BeginPasskeyLogin = Depends(get_begin_passkey_login_use_case),
) -> PasskeyChallenge:
    """Options for navigator.credentials.get() and the challenge token the
    login request sends back. They name no credentials, so they reveal
    nothing about which accounts hold passkeys."""
    return use_case.execute()


@router.post("/login/passkey", response_model=TokenResponse)
async def login_passkey(
    body: PasskeyLoginRequest,
    request: Request,
    response: Response,
    use_case: PasskeyLogin = Depends(get_passkey_login_use_case),
) -> TokenResponse:
    """Exchange a signed passkey assertion for a session. No TOTP step
    follows: the passkey already proved the device and the user.

    Answers 401 PasskeyRejectedError for any assertion that did not verify,
    403 PasskeyPasswordRequiredError when a directory account has to sign in
    with its password first, and 403 InactiveUserError or 503
    MaintenanceModeError like the password login."""
    cmd = PasskeyLoginCommand(
        challenge_token=body.challenge_token,
        credential=body.credential,
        client_ip=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    result = await use_case.execute(cmd)
    return session_response(response, result)
