"""
Repository interface for the PDM poller's cold-folder cadence state
(domain.services.pdm_poll_cadence). PollPdmVault reads a vault's states once
per run, upserts unchanged folders to advance their backoff and resets
folders that changed. RefreshPdmFile also resets a folder after a single-file
ingest, so a trigger keeps its folder warm.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.external_data.domain.entities.pdm_folder_poll_state import PdmFolderPollState


@runtime_checkable
class IPdmFolderPollStateRepository(Protocol):
    async def get_all_for_vault(self, vault_id: str) -> dict[str, PdmFolderPollState]:
        """Every known cadence state row of the vault, keyed by its own
        `folder_key`."""
        ...

    async def upsert(self, state: PdmFolderPollState) -> None:
        """Inserts or updates the (vault_id, folder_key) row of `state`. Does
        not commit."""
        ...

    async def reset(self, vault_id: str, folder_key: str) -> None:
        """Clears the (vault_id, folder_key) row back to the base interval and
        stamps last_changed_at. A missing row is a no-op, since such a folder is
        already due on its next walk. Does not commit."""
        ...
