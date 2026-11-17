"""
Append-only record of every request authenticated with a given API key.
Written by DatabaseLoggingMiddleware for every request (not just writes,
unlike the general HTTP log_table) so key usage can be audited.
"""

from dataclasses import dataclass
from datetime import datetime

from src.shared_kernel.domain.entities.base import Entity


@dataclass
class ApiKeyUsageLogEntry(Entity):
    key_id: int
    called_at: datetime
    method: str
    path: str
    status_code: int | None
