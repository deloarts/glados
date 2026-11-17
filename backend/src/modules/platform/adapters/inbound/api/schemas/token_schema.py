"""HTTP schemas for authentication tokens: bearer tokens, TOTP challenges, and 2FA
enrolment setup responses."""

from pydantic import BaseModel

from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel


class TokenResponse(ResponseModel):
    access_token: str
    token_type: str


class TOTPChallengeResponse(ResponseModel):
    totp_required: bool = True
    partial_token: str
    # How long "trust this device" would skip this prompt, from admin
    # security settings. 0 = feature disabled; the UI hides the checkbox.
    trusted_device_days: int = 0


class TOTPSetupRequiredResponse(ResponseModel):
    """Third login outcome: credentials were correct, but 2FA is mandatory
    and this user has not enrolled yet.

    `username` is included because the setup token is refused by every
    normal route, the enrolment screen cannot call /users/me to find out
    who is signing in, so it would otherwise have nothing to display.
    """

    totp_setup_required: bool = True
    setup_token: str
    username: str


class TokenPayload(BaseModel):
    sub: str | int | bool | None = None
