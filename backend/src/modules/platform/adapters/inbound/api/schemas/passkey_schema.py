"""HTTP request and response schemas for passkeys: the passkey login, registering a
passkey for the acting user, and listing and removing passkeys.

`credential` is the browser's PublicKeyCredential in its JSON form (what
PublicKeyCredential.toJSON() returns), passed through to the verifier as is.
"""

from typing import Any

from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.application.dto.passkey_dto import PasskeyChallenge
from src.modules.platform.application.dto.passkey_dto import PasskeyResult
from src.modules.platform.domain.entities.passkey import PASSKEY_NAME_MAX_LENGTH

__all__ = [
    "PasskeyChallenge",
    "PasskeyLoginRequest",
    "PasskeyRegisterRequest",
    "PasskeyRegistrationOptionsRequest",
    "PasskeyRenameRequest",
    "PasskeyResult",
]


class PasskeyLoginRequest(BaseModel):
    challenge_token: str
    credential: dict[str, Any]


class PasskeyRegistrationOptionsRequest(BaseModel):
    """The acting user's current password, confirmed before a passkey may
    be added to the account."""

    password: str = Field(min_length=1)


class PasskeyRegisterRequest(BaseModel):
    challenge_token: str
    credential: dict[str, Any]
    name: str = Field(default="", max_length=PASSKEY_NAME_MAX_LENGTH)


class PasskeyRenameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=PASSKEY_NAME_MAX_LENGTH, pattern=r"\S")
