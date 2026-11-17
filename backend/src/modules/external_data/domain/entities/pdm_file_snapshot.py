"""
One row per PDM vault file under a watched folder: what the last poll saw and
where the file stands in the poll and ingest pipeline (`sync_state`). It is
the poller's diff base and covers files never ingested too (see
docs/reference/field-ownership.md sections 4 and 5).

`kind` is None while a file under a `by_kind` folder has no readable kind
variable. Files under a `documents` folder get the singular "document", so
the made and bought conflict check never confuses it with the folder's own
"documents" kind. `article_name` is stored only for the catalogue preview.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class PdmFileSnapshot(Entity):
    vault_id: str
    file_id: int
    kind: str | None  # "made" | "bought" | None (unresolved, by_kind folder)
    name: str
    path: str
    parent_folder_id: int
    version: int
    state_id: int
    state: str
    modified_at: datetime | None
    first_seen_at: datetime
    last_seen_at: datetime
    last_ingested_version: int | None
    sync_state: PdmFileSyncState
    last_error: str | None
    part_number: str | None
    revision: str | None
    item_id: int | None
    # Variables of a parked conflict, so the retry at the end of every poll
    # run can re-attempt IngestPdmFile without re-reading them from PDM.
    parked_payload: dict[str, str] | None
    # Defaults to None because only ingest and the repository mapper set it.
    article_name: str | None = None
