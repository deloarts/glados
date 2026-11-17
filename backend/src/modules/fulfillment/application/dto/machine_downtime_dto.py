"""
DTOs for the MachineDowntime aggregate.
"""

from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator
from pydantic import BaseModel
from pydantic import Field

from src.modules.fulfillment.domain.value_objects.machine_downtime_reason import (
    MachineDowntimeReason,
)
from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.base import ResultModel
from src.shared_kernel.domain.services.clock import as_utc

# ══════════════════════════════════════════════════════════════════════
# Commands
# ══════════════════════════════════════════════════════════════════════


# A naive time is read as UTC, so it compares with the stored ones.
_UtcDatetime = Annotated[datetime, AfterValidator(as_utc)]


class AddMachineDowntimeCommand(BaseModel):
    machine_id: int
    started_at: _UtcDatetime
    ended_at: _UtcDatetime | None = None
    reason: MachineDowntimeReason
    note: str | None = None


class UpdateMachineDowntimeCommand(BaseModel):
    started_at: _UtcDatetime
    ended_at: _UtcDatetime | None = None
    reason: MachineDowntimeReason
    note: str | None = None


class EndMachineDowntimeCommand(BaseModel):
    ended_at: _UtcDatetime | None = None  # defaults to now when omitted


# ══════════════════════════════════════════════════════════════════════
# Results
# ══════════════════════════════════════════════════════════════════════


class MachineDowntimeResult(ResultBase):
    created: datetime
    changed: datetime | None
    machine_id: int
    machine_internal_name: str
    started_at: datetime
    ended_at: datetime | None
    reason: str
    note: str | None
    reported_by_id: int
    reported_by_full_name: str
    ended_by_id: int | None
    ended_by_full_name: str | None
    changed_by_id: int | None
    changed_by_full_name: str | None
    changes: list[str] = Field(default_factory=list)


class OpenMachineDowntimeResult(ResultModel):
    """An open downtime of a machine, embedded in the machine so the list and
    detail views can show the badge without a second request."""

    id: int
    started_at: datetime
    reason: MachineDowntimeReason
