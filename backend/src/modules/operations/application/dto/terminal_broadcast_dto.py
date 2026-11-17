"""
Commands and results for messages to terminals: sending one, its audience
and how many terminals that reaches, and the active messages as the
terminals page lists them. What a device receives is
TerminalBroadcastMessage in terminal_dto.py, which carries no author.
"""

from datetime import datetime

from pydantic import AwareDatetime
from pydantic import BaseModel
from pydantic import Field

from src.modules.operations.application.dto.terminal_dto import BroadcastSeverityValue
from src.modules.operations.application.dto.terminal_dto import BroadcastStyleValue
from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.base import ResultModel
from src.modules.platform.application.dto.user_dto import PublicUserResult


class TerminalBroadcastAudienceCommand(BaseModel):
    """Every terminal, or the terminals picked plus those showing a picked
    infoscreen."""

    all_terminals: bool = True
    terminal_ids: list[int] = Field(default_factory=list)
    infoscreen_ids: list[int] = Field(default_factory=list)


class SendTerminalBroadcastCommand(TerminalBroadcastAudienceCommand):
    text: str
    severity: BroadcastSeverityValue = "info"
    style: BroadcastStyleValue = "banner"
    show_until: AwareDatetime


class TerminalBroadcastReachResult(ResultModel):
    """How many approved terminals an audience reaches now."""

    count: int


class TerminalBroadcastResult(ResultBase):
    text: str
    severity: BroadcastSeverityValue
    style: BroadcastStyleValue
    show_until: datetime
    all_terminals: bool
    terminal_ids: list[int]
    infoscreen_ids: list[int]
    created: datetime
    created_by: PublicUserResult | None
    ended_at: datetime | None
    # Approved terminals the message reaches now.
    reach_count: int
