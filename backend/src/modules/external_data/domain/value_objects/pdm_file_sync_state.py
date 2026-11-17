"""
States for a PdmFileSnapshot row's `sync_state`: where a watched PDM file
currently stands in the poll -> ingest pipeline, distinct from the item
link column PdmSyncState (pdm_sync_state.py), which tracks an already
ingested item's own sync status. The entity keeps a plain `sync_state: str`
field, mirroring PrintJobStatus's precedent (print_classifier.py); the
application layer constructs/compares with this enum, the repository
stores/reads the plain value.
"""

from enum import Enum
from enum import unique


@unique
class PdmFileSyncState(str, Enum):
    PENDING = "pending"
    INGESTED = "ingested"
    SKIPPED = "skipped"
    MISSING = "missing"
    CONFLICT = "conflict"
    ERROR = "error"
