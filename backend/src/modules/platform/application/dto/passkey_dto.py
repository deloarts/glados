"""
Commands and results of the passkey use cases: registering and managing
the acting user's own passkeys, and the passkey login. These cross the
application boundary, not the same as API schemas.

Secrets (passwords, challenge tokens) are kept out of repr so a logged or
printed DTO never carries them.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.base import ResultModel


class PasskeyResult(ResultBase):
    """A passkey as shown in the account UI. Never includes the key material
    or the credential ID, there is nothing displayable in them."""

    name: str
    created_at: datetime
    last_used_at: datetime | None
    backed_up: bool


class PasskeyChallenge(ResultModel):
    """The options the browser passes to navigator.credentials, and the
    token the verify request has to send back with the browser's answer."""

    options: dict[str, Any]
    challenge_token: str = Field(repr=False)


class RegisterPasskeyCommand(BaseModel):
    challenge_token: str = Field(repr=False)
    credential: dict[str, Any]
    name: str


class PasskeyLoginCommand(BaseModel):
    challenge_token: str = Field(repr=False)
    credential: dict[str, Any]
    client_ip: str | None
    user_agent: str | None
