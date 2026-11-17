"""HTTP response schemas for user session operations: current session info, session listing,
and session revocation counts."""

from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.platform.application.dto.session_dto import CurrentSessionResult
from src.modules.platform.application.dto.session_dto import SessionResult
from src.modules.platform.application.dto.session_dto import TrustedDeviceResult

__all__ = [
    "CurrentSessionResult",
    "RevokedCountResult",
    "SessionResult",
    "TrustedDeviceResult",
]


class RevokedCountResult(ResponseModel):
    revoked: int
