"""
One row per API call authenticated with a personal access token, recording
when it was called, the method and path, and the resulting status code.
Forms the audit trail used to review or revoke a token's usage.
"""

from dataclasses import dataclass
from datetime import datetime

from src.shared_kernel.domain.entities.base import Entity


@dataclass
class PatUsageLogEntry(Entity):
    pat_id: int
    called_at: datetime
    method: str
    path: str
    status_code: int | None
