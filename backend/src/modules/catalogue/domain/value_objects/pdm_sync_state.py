"""
Sync-axis states for MadeItem/BoughtItem link columns (`pdm_sync_state`),
independent of the catalogue `status` field: a row can be `replaced` and
`missing` at once. See docs/reference/field-ownership.md sections 1.4 and 4. The entity
keeps a plain `pdm_sync_state: str | None` field, mirroring PrintJobStatus's
precedent (print_classifier.py); the application layer constructs/compares
with this enum, the repository stores/reads the plain value.
"""

from enum import Enum
from enum import unique


@unique
class PdmSyncState(str, Enum):
    SYNCED = "synced"
    MISSING = "missing"
    CONFLICT = "conflict"
