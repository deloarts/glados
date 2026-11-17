"""OAuth2 password login for the web surface.

The login policy lives in PasswordLogin. This route reads the form and the
trusted-device cookie, and turns the outcome into the response: a session
cookie and bearer token, a TOTP challenge, or a forced enrolment.
"""

from fastapi import Depends
from fastapi import HTTPException
from fastapi import Request
from fastapi import Response
from fastapi import status
from fastapi.routing import APIRouter
from fastapi.security import OAuth2PasswordRequestForm

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.auth import get_password_login_use_case
from src.modules.platform.adapters.inbound.api.schemas.token_schema import TokenResponse
from src.modules.platform.adapters.inbound.api.schemas.token_schema import TOTPChallengeResponse
from src.modules.platform.adapters.inbound.api.schemas.token_schema import TOTPSetupRequiredResponse
from src.modules.platform.adapters.inbound.api.v1.auth.login_responses import client_ip
from src.modules.platform.adapters.inbound.api.v1.auth.login_responses import session_response
from src.modules.platform.adapters.inbound.api.v1.auth.login_responses import too_many_attempts
from src.modules.platform.application.dto.login_dto import PasswordLoginCommand
from src.modules.platform.application.dto.login_dto import SessionIssued
from src.modules.platform.application.dto.login_dto import TotpChallengeIssued
from src.modules.platform.application.use_cases.auth.password_login import PasswordLogin
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import LoginLockedError
from src.modules.platform.domain.exceptions import UserNotFoundError
from src.modules.platform.infrastructure.security.trusted_device import TRUSTED_DEVICE_COOKIE

router = APIRouter()


@router.post(
    "/login/access-token",
    response_model=TokenResponse | TOTPChallengeResponse | TOTPSetupRequiredResponse,
)
async def login_access_token(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    use_case: PasswordLogin = Depends(get_password_login_use_case),
) -> TokenResponse | TOTPChallengeResponse | TOTPSetupRequiredResponse:
    """OAuth2 password login. The `username` field accepts a username or an
    e-mail address. Returns a bearer token, or a TOTP challenge if 2FA is on."""
    cmd = PasswordLoginCommand(
        username=form_data.username,
        password=form_data.password,
        client_ip=client_ip(request),
        user_agent=request.headers.get("user-agent"),
        trusted_device_secret=request.cookies.get(TRUSTED_DEVICE_COOKIE),
    )
    try:
        result = await use_case.execute(cmd)
    except LoginLockedError as e:
        raise too_many_attempts(e) from e
    except UserNotFoundError as e:
        # A wrong password, an unknown name and a directory outage
        # (CredentialsUnverifiableError) all answer this same 401, so the
        # response cannot tell them apart.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password"
        ) from e

    if isinstance(result, SessionIssued):
        return session_response(response, result)
    if isinstance(result, TotpChallengeIssued):
        return TOTPChallengeResponse(
            partial_token=result.partial_token,
            trusted_device_days=result.trusted_device_days,
        )
    return TOTPSetupRequiredResponse(setup_token=result.setup_token, username=result.username)


@router.post(
    "/login/test-token",
    response_model=dict,
)
async def test_token(
    _: User = Depends(get_current_active_user),
) -> dict[str, str]:
    """Validate the caller's session token. The frontend calls this on load
    to decide whether it still has a live session; a missing/expired/forged
    token is rejected by the dependency with 401 before this body runs."""
    return {"detail": "Token is valid"}
