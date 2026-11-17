"""
Poll cadence state of one watched folder for the PDM poller's cold-folder
backoff (domain.services.pdm_poll_cadence), keyed by (vault_id, folder_key).
A folder is due when `next_due_at` is unset or past. An unchanged scheduled
walk pushes it further out, while any activity resets it to the base
interval. A manual sync and the initial poll ignore this state and walk
everything.
"""

from dataclasses import dataclass
from datetime import datetime

from src.shared_kernel.domain.entities.base import Entity


@dataclass
class PdmFolderPollState(Entity):
    vault_id: str
    folder_key: str
    consecutive_unchanged_runs: int
    next_due_at: datetime | None
    last_changed_at: datetime | None
    updated_at: datetime
