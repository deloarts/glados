"""
Step 2 of 2FA login: exchange a partial token + TOTP code for a full bearer token.

The login policy lives in TotpLogin. This route builds the command from the
body and the request, sets the session and trusted-device cookies, and
answers the refusals that carry no error code.
"""

from fastapi import Depends
from fastapi import HTTPException
from fastapi import Request
from fastapi import Response
from fastapi import status
from fastapi.routing import APIRouter
from pydantic import BaseModel

from src.modules.platform.adapters.inbound.api.deps.auth import get_totp_login_use_case
from src.modules.platform.adapters.inbound.api.schemas.token_schema import TokenResponse
from src.modules.platform.adapters.inbound.api.v1.auth.login_responses import client_ip
from src.modules.platform.adapters.inbound.api.v1.auth.login_responses import session_response
from src.modules.platform.adapters.inbound.api.v1.auth.login_responses import too_many_attempts
from src.modules.platform.application.dto.login_dto import TotpLoginCommand
from src.modules.platform.application.use_cases.auth.totp_login import TotpLogin
from src.modules.platform.domain.exceptions import InactiveUserError
from src.modules.platform.domain.exceptions import LoginLockedError
from src.modules.platform.domain.exceptions import TOTPNotEnabledError

router = APIRouter()


class TOTPLoginRequest(BaseModel):
    partial_token: str
    totp_code: str
    # "Trust this device": remember the successful second factor in an
    # httpOnly cookie so future logins skip the TOTP prompt. Honoured only
    # while totp_trusted_device_days > 0 in admin security settings.
    trust_device: bool = False


@router.post("/login/totp", response_model=TokenResponse)
async def login_totp(
    body: TOTPLoginRequest,
    request: Request,
    response: Response,
    use_case: TotpLogin = Depends(get_totp_login_use_case),
) -> TokenResponse:
    """Exchange a TOTP challenge token + one-time code for a full bearer token."""
    cmd = TotpLoginCommand(
        partial_token=body.partial_token,
        totp_code=body.totp_code,
        trust_device=body.trust_device,
        client_ip=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    try:
        result = await use_case.execute(cmd)
    except LoginLockedError as e:
        raise too_many_attempts(e) from e
    except InactiveUserError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive"
        ) from e
    except TOTPNotEnabledError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="2FA is not enabled for this account"
        ) from e
    return session_response(response, result)
