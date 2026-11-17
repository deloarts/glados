"""
Input commands and output results for personal access token (PAT) use cases.
These cross the application boundary, not the same as API schemas.
"""

from datetime import datetime

from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.base import ResultModel

# ── Commands (inbound) ────────────────────────────────────────────────


class CreatePatCommand(BaseModel):
    name: str = Field(..., min_length=1)
    permissions: list[str] = Field(default_factory=list)
    # None = never expires, which the security settings refuse while their
    # token_max_lifetime_days cap is above 0 (TokenExpiryRequiredError).
    # le=36500 (100 years) is the wire-boundary ceiling only; the enforced
    # cap is that setting (default 365), applied at creation through
    # domain/services/token_lifetime.py.
    expires_in_days: int | None = Field(default=None, gt=0, le=36500)


# ── Results (outbound) ────────────────────────────────────────────────


class PatResult(ResultBase):
    """PAT as shown in the web UI, never includes the raw token value."""

    name: str
    token_prefix: str
    permissions: list[str]
    created: datetime
    expires_at: datetime | None
    revoked_at: datetime | None
    is_expired: bool


class CreatedPatResult(PatResult):
    """Returned exactly once, on creation, the only time the raw token value is visible."""

    token: str


class RevokeAllPatsResult(ResultModel):
    revoked_count: int


class PatUsageLogEntryResult(ResultBase):
    pat_id: int
    called_at: datetime
    method: str
    path: str
    status_code: int | None
