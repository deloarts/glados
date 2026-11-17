"""
What ReconcilePdmVault found wrong between the vault, the snapshot
table and the item catalogues. `orphaned_cad_row`, `revision_lag` and
`kind_mismatch` compare a CAD-owned item row against its own linked
snapshot; `duplicate_part_number` compares snapshots/registry entries/items
against each other; `stuck_file` and `document_unmatched` are the two
categories PdmReconciliationFinding.count actually aggregates (one row per
distinct reason+kind rather than one row per file, see that entity's
docstring); `document_missing` mirrors orphaned_cad_row for the document
link table; `unclaimed_match` surfaces an unlinked bought item PDM ingest
would now claim; `writeback_drift` only exists in deep mode (application.
services.pdm_reconciliation), reading the vault's own Glados.* datacard
variables back to check them against what Glados actually has.

`status_mismatch`, `replaced_without_successor` and
`successor_without_replaced` are the lifecycle status feature's own three
(docs/PDM_INTEGRATION.md's "lifecycle mapping" section): `status_mismatch`
compares a linked CAD row's stored `status` against the status implied by
its snapshot's own workflow state id (a state outside every configured
list is ignored, not a mismatch); the other two are pure row-consistency
checks: a `replaced` row with no successor, or a successor set on a row
that isn't `replaced`, and need no snapshot at all, only the CAD rows
ReconcilePdmVault already loads.

`part_number_drift` compares a linked row's own `part_number` against the
part number its `pdm_file_snapshot` row currently carries. Report only,
quick mode, no vault call: ingest never overwrites `part_number` on an
already-linked row (docs/PDM_INTEGRATION.md section 8), so this is the
only place the drift is ever surfaced.
"""

from enum import Enum
from enum import unique


@unique
class PdmReconciliationCategory(str, Enum):
    ORPHANED_CAD_ROW = "orphaned_cad_row"
    STUCK_FILE = "stuck_file"
    REVISION_LAG = "revision_lag"
    DUPLICATE_PART_NUMBER = "duplicate_part_number"
    KIND_MISMATCH = "kind_mismatch"
    DOCUMENT_MISSING = "document_missing"
    DOCUMENT_UNMATCHED = "document_unmatched"
    UNCLAIMED_MATCH = "unclaimed_match"
    WRITEBACK_DRIFT = "writeback_drift"
    STATUS_MISMATCH = "status_mismatch"
    REPLACED_WITHOUT_SUCCESSOR = "replaced_without_successor"
    SUCCESSOR_WITHOUT_REPLACED = "successor_without_replaced"
    PART_NUMBER_DRIFT = "part_number_drift"
