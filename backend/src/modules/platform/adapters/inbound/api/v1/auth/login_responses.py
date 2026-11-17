"""
The HTTP half of the two login routes: reading the client address, turning
a lockout into its 429, and writing a finished login's cookies and token
body. The login policy itself lives in PasswordLogin and TotpLogin.
"""

from fastapi import HTTPException
from fastapi import Request
from fastapi import Response
from fastapi import status

from src.modules.platform.adapters.inbound.api.schemas.token_schema import TokenResponse
from src.modules.platform.application.dto.login_dto import SessionIssued
from src.modules.platform.domain.exceptions import LoginLockedError
from src.modules.platform.infrastructure.config.settings import cfg
from src.modules.platform.infrastructure.security.session_cookie import set_session_cookie
from src.modules.platform.infrastructure.security.trusted_device import TRUSTED_DEVICE_COOKIE

TRUSTED_DEVICE_COOKIE_PATH = "/api/v1/auth"


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def too_many_attempts(exc: LoginLockedError) -> HTTPException:
    """The lockout answer of both login steps. It carries no error code and
    tells the client through Retry-After how long the lock still holds."""
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many failed attempts. Try again later.",
        headers={"Retry-After": str(exc.retry_after_seconds)},
    )


def session_response(response: Response, result: SessionIssued) -> TokenResponse:
    """Sets the trusted-device cookie when the login granted one, then the
    session cookie, and returns the bearer token body."""
    if result.trusted_device is not None:
        # httpOnly: the secret must survive sign-out yet stay invisible to
        # page scripts. Path-scoped to the auth surface, no other route
        # ever needs it. secure=False only in debug (plain-http dev).
        response.set_cookie(
            TRUSTED_DEVICE_COOKIE,
            result.trusted_device.secret,
            max_age=result.trusted_device.max_age_seconds,
            path=TRUSTED_DEVICE_COOKIE_PATH,
            httponly=True,
            samesite="lax",
            secure=not cfg.debug,
        )
    set_session_cookie(response, result.access_token, result.cookie_max_age)
    return TokenResponse(access_token=result.access_token, token_type="bearer")
