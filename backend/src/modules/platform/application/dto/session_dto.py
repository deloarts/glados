"""
Output results for session and trusted-device self-service use cases.
These cross the application boundary, not the same as API schemas.
"""

from datetime import datetime

from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.base import ResultModel


class CurrentSessionResult(ResultModel):
    """Shape for GET /users/me/sessions/current, the countdown's data
    source. Not a ResultBase subtype: it answers "when does the session
    making this request expire," not a row with an id of its own."""

    expires_at: datetime | None
    server_time: datetime


class SessionResult(ResultBase):
    """A live session as shown in the account's sessions list."""

    created_at: datetime
    last_seen_at: datetime
    user_agent: str | None
    ip: str | None
    is_current: bool


class TrustedDeviceResult(ResultBase):
    """A trusted-device grant (TOTP skip) as shown in the account UI.
    Never includes the token hash, there is nothing displayable in it."""

    created_at: datetime
    last_used_at: datetime
    expires_at: datetime
    user_agent: str | None
