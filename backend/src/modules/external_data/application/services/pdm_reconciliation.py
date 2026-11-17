"""Pure finders behind the PDM reconciliation report (docs/reference/pdm-admin.md
section 7), one per category, working on data the use case loaded in
bulk. CadRowRef is the shape they need from a made or bought item, so they
depend on neither entity.

unclaimed_match and the deep-mode writeback_drift need per-item lookups
and live in ReconcilePdmVault instead. Three separate checks report under
duplicate_part_number, so the dialog counts part-number problems rather
than which check found them.
"""

from collections import defaultdict
from collections.abc import Iterable
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta

from src.modules.catalogue.domain.entities.part_number_registry import PartNumberRegistryEntry
from src.modules.external_data.application.services.pdm_skip_reasons import is_deliberate_skip
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.entities.pdm_document_link import PdmDocumentLink
from src.modules.external_data.domain.entities.pdm_file_snapshot import PdmFileSnapshot
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from src.modules.external_data.domain.value_objects.pdm_reconciliation_category import (
    PdmReconciliationCategory,
)
from src.modules.external_data.domain.value_objects.pdm_reconciliation_severity import (
    PdmReconciliationSeverity,
)
from src.modules.platform.infrastructure.logging.logger import log

# Sync states a snapshot can be "stuck" in: never successfully ingested,
# not simply new. INGESTED and MISSING are excluded on purpose: MISSING has
# its own remediation path (the poller's missing sweep / orphaned_cad_row),
# not a staleness problem.
_STUCK_STATES = frozenset(
    {
        PdmFileSyncState.PENDING.value,
        PdmFileSyncState.ERROR.value,
        PdmFileSyncState.CONFLICT.value,
        PdmFileSyncState.SKIPPED.value,
    }
)

_DOCUMENT_KIND = "document"


@dataclass(frozen=True)
class ReconciliationFinding:
    """One category function's output row, before ReconcilePdmVault turns
    it into a PdmReconciliationFinding entity (adding run_id/created_at)."""

    category: str
    severity: str
    kind: str | None
    item_id: int | None
    file_id: int | None
    part_number: str | None
    revision: str | None
    message: str
    count: int = 1


@dataclass(frozen=True)
class CadRowRef:
    """What the finders need from one CAD-owned made or bought item."""

    item_id: int
    kind: str  # "made" | "bought"
    vault_id: str | None
    pdm_file_id: int | None
    pdm_file_version: int | None
    part_number: str | None
    revision: str | None  # None for a bought item, never revisioned
    status: str  # "active" | "inactive" | "replaced"
    successor_item_id: int | None


SnapshotKey = tuple[str, int]  # (vault_id, file_id)


def index_snapshots_by_file(
    snapshots: Iterable[PdmFileSnapshot],
) -> dict[SnapshotKey, PdmFileSnapshot]:
    """The snapshots keyed by (vault_id, file_id)."""
    return {(s.vault_id, s.file_id): s for s in snapshots}


def _resolve_snapshot(
    row: CadRowRef, snapshots_by_key: Mapping[SnapshotKey, PdmFileSnapshot]
) -> PdmFileSnapshot | None:
    """The linked snapshot of a row. A file id without a vault id is a data
    inconsistency, since ingest writes both, and is logged as one."""
    assert row.pdm_file_id is not None  # every caller has already checked this
    if row.vault_id is None:
        log.warning(
            "PDM reconciliation: item #%s (kind=%s) has pdm_file_id=%s but no vault_id - "
            "data inconsistency, skipping snapshot lookup.",
            row.item_id,
            row.kind,
            row.pdm_file_id,
        )
        return None
    return snapshots_by_key.get((row.vault_id, row.pdm_file_id))


def find_orphaned_cad_rows(
    rows: Iterable[CadRowRef], snapshots_by_key: Mapping[SnapshotKey, PdmFileSnapshot]
) -> list[ReconciliationFinding]:
    """A CAD-owned item with no linked PDM file id, or one whose linked
    file has no snapshot row, or whose snapshot is `missing`."""
    findings: list[ReconciliationFinding] = []
    for row in rows:
        if row.pdm_file_id is None:
            reason = "CAD item has no linked PDM file id"
        else:
            snapshot = _resolve_snapshot(row, snapshots_by_key)
            if snapshot is None:
                reason = (
                    "PDM file id set with no vault_id (data inconsistency)"
                    if row.vault_id is None
                    else "no snapshot found for the linked PDM file"
                )
            elif snapshot.sync_state == PdmFileSyncState.MISSING.value:
                reason = "linked PDM file is missing"
            else:
                continue
        findings.append(
            ReconciliationFinding(
                category=PdmReconciliationCategory.ORPHANED_CAD_ROW.value,
                severity=PdmReconciliationSeverity.WARNING.value,
                kind=row.kind,
                item_id=row.item_id,
                file_id=row.pdm_file_id,
                part_number=row.part_number,
                revision=row.revision,
                message=reason,
            )
        )
    return findings


def find_revision_lag(
    rows: Iterable[CadRowRef], snapshots_by_key: Mapping[SnapshotKey, PdmFileSnapshot]
) -> list[ReconciliationFinding]:
    """The snapshot's version differs from the item's in either direction."""
    findings: list[ReconciliationFinding] = []
    for row in rows:
        if row.pdm_file_id is None:
            continue
        snapshot = _resolve_snapshot(row, snapshots_by_key)
        if snapshot is None:
            continue
        item_version = row.pdm_file_version if row.pdm_file_version is not None else -1
        if snapshot.version > item_version:
            message = (
                f"PDM file is at version {snapshot.version}, Glados item is at version "
                f"{row.pdm_file_version}"
            )
        elif item_version > snapshot.version:
            message = (
                f"Glados item is at version {row.pdm_file_version}, ahead of the PDM "
                f"snapshot's version {snapshot.version}"
            )
        else:
            continue
        findings.append(
            ReconciliationFinding(
                category=PdmReconciliationCategory.REVISION_LAG.value,
                severity=PdmReconciliationSeverity.WARNING.value,
                kind=row.kind,
                item_id=row.item_id,
                file_id=row.pdm_file_id,
                part_number=row.part_number,
                revision=row.revision,
                message=message,
            )
        )
    return findings


def find_kind_mismatches(
    rows: Iterable[CadRowRef], snapshots_by_key: Mapping[SnapshotKey, PdmFileSnapshot]
) -> list[ReconciliationFinding]:
    """The snapshot's kind disagrees with the item's, usually because the
    file moved or was relabelled since it was linked."""
    findings: list[ReconciliationFinding] = []
    for row in rows:
        if row.pdm_file_id is None:
            continue
        snapshot = _resolve_snapshot(row, snapshots_by_key)
        if snapshot is None or snapshot.kind is None or snapshot.kind == row.kind:
            continue
        findings.append(
            ReconciliationFinding(
                category=PdmReconciliationCategory.KIND_MISMATCH.value,
                severity=PdmReconciliationSeverity.ERROR.value,
                kind=row.kind,
                item_id=row.item_id,
                file_id=row.pdm_file_id,
                part_number=row.part_number,
                revision=row.revision,
                message=f"snapshot kind is {snapshot.kind!r}, linked item is {row.kind!r}",
            )
        )
    return findings


def find_status_mismatches(
    rows: Iterable[CadRowRef],
    snapshots_by_key: Mapping[SnapshotKey, PdmFileSnapshot],
    settings: AdminPdmSettings,
) -> list[ReconciliationFinding]:
    """A linked row whose status differs from the one its workflow state
    implies. Unwatched states are never compared."""
    findings: list[ReconciliationFinding] = []
    for row in rows:
        if row.pdm_file_id is None:
            continue
        snapshot = _resolve_snapshot(row, snapshots_by_key)
        if snapshot is None:
            continue
        if snapshot.state_id in settings.released_state_ids_for(row.kind):
            implied = "active"
        elif snapshot.state_id in settings.obsolete_state_ids_for(row.kind):
            implied = "inactive"
        elif snapshot.state_id in settings.replaced_state_ids_for(row.kind):
            implied = "replaced"
        else:
            continue
        if row.status == implied:
            continue
        findings.append(
            ReconciliationFinding(
                category=PdmReconciliationCategory.STATUS_MISMATCH.value,
                severity=PdmReconciliationSeverity.WARNING.value,
                kind=row.kind,
                item_id=row.item_id,
                file_id=row.pdm_file_id,
                part_number=row.part_number,
                revision=row.revision,
                message=(
                    f"item status is {row.status!r}, PDM state {snapshot.state!r} implies "
                    f"{implied!r}"
                ),
            )
        )
    return findings


def find_replaced_without_successor(rows: Iterable[CadRowRef]) -> list[ReconciliationFinding]:
    """A `replaced` row without a successor. PDM never sets successors, so
    this is an unfinished web action."""
    findings: list[ReconciliationFinding] = []
    for row in rows:
        if row.status != "replaced" or row.successor_item_id is not None:
            continue
        findings.append(
            ReconciliationFinding(
                category=PdmReconciliationCategory.REPLACED_WITHOUT_SUCCESSOR.value,
                severity=PdmReconciliationSeverity.WARNING.value,
                kind=row.kind,
                item_id=row.item_id,
                file_id=row.pdm_file_id,
                part_number=row.part_number,
                revision=row.revision,
                message="status is 'replaced' with no successor_item_id set",
            )
        )
    return findings


def find_successor_without_replaced(rows: Iterable[CadRowRef]) -> list[ReconciliationFinding]:
    """A row with a successor whose status is not `replaced`."""
    findings: list[ReconciliationFinding] = []
    for row in rows:
        if row.successor_item_id is None or row.status == "replaced":
            continue
        findings.append(
            ReconciliationFinding(
                category=PdmReconciliationCategory.SUCCESSOR_WITHOUT_REPLACED.value,
                severity=PdmReconciliationSeverity.WARNING.value,
                kind=row.kind,
                item_id=row.item_id,
                file_id=row.pdm_file_id,
                part_number=row.part_number,
                revision=row.revision,
                message=(
                    f"successor_item_id is set (#{row.successor_item_id}) but status is "
                    f"{row.status!r}, not 'replaced'"
                ),
            )
        )
    return findings


def find_part_number_drift(
    rows: Iterable[CadRowRef], snapshots_by_key: Mapping[SnapshotKey, PdmFileSnapshot]
) -> list[ReconciliationFinding]:
    """A linked row whose part number differs from its snapshot's. Report
    only, since ingest never renumbers a linked row. Revision rows sharing
    one file count as one finding."""
    families: dict[SnapshotKey, list[CadRowRef]] = defaultdict(list)
    snapshot_by_family: dict[SnapshotKey, PdmFileSnapshot] = {}
    for row in rows:
        if row.pdm_file_id is None:
            continue
        snapshot = _resolve_snapshot(row, snapshots_by_key)
        if snapshot is None or row.vault_id is None:
            continue
        key = (row.vault_id, row.pdm_file_id)
        families[key].append(row)
        snapshot_by_family[key] = snapshot

    findings: list[ReconciliationFinding] = []
    for key, family in families.items():
        snapshot = snapshot_by_family[key]
        snapshot_part_number = (snapshot.part_number or "").strip()
        if not snapshot_part_number:
            continue
        row = family[0]
        item_part_number = (row.part_number or "").strip()
        if item_part_number == snapshot_part_number:
            continue
        findings.append(
            ReconciliationFinding(
                category=PdmReconciliationCategory.PART_NUMBER_DRIFT.value,
                severity=PdmReconciliationSeverity.WARNING.value,
                kind=row.kind,
                item_id=row.item_id,
                file_id=row.pdm_file_id,
                part_number=row.part_number,
                revision=row.revision,
                message=(
                    f"item part number is {row.part_number!r}, PDM file's snapshot has "
                    f"{snapshot.part_number!r}, applied on the file's next ingest"
                ),
                count=len(family),
            )
        )
    return findings


def find_stuck_files(
    snapshots: Iterable[PdmFileSnapshot], *, stuck_after_days: int, now: datetime
) -> list[ReconciliationFinding]:
    """Snapshots unresolved for longer than `stuck_after_days`, one finding
    per reason and kind. A deliberate skip (an unwatched state, a private
    file, a dismissed row) is not stuck, and documents are left to
    find_document_unmatched, so no row is reported twice."""
    groups: dict[tuple[str, str | None], int] = defaultdict(int)
    threshold = now - timedelta(days=stuck_after_days)
    for snapshot in snapshots:
        if snapshot.sync_state not in _STUCK_STATES or snapshot.kind == _DOCUMENT_KIND:
            continue
        if snapshot.sync_state == PdmFileSyncState.SKIPPED.value and is_deliberate_skip(
            snapshot.last_error
        ):
            continue
        if snapshot.last_seen_at > threshold:
            continue
        reason = snapshot.last_error or f"stuck in {snapshot.sync_state.value}"
        groups[(reason, snapshot.kind)] += 1

    return [
        ReconciliationFinding(
            category=PdmReconciliationCategory.STUCK_FILE.value,
            severity=PdmReconciliationSeverity.WARNING.value,
            kind=kind,
            item_id=None,
            file_id=None,
            part_number=None,
            revision=None,
            message=reason,
            count=count,
        )
        for (reason, kind), count in groups.items()
    ]


def find_duplicate_snapshot_part_numbers(
    snapshots: Iterable[PdmFileSnapshot],
) -> list[ReconciliationFinding]:
    """Two or more snapshots (any kind) sharing the same non-blank part
    number. Each such number is one finding, `count` the number of files
    that share it."""
    groups: dict[str, list[PdmFileSnapshot]] = defaultdict(list)
    for snapshot in snapshots:
        if snapshot.part_number:
            groups[snapshot.part_number].append(snapshot)

    findings: list[ReconciliationFinding] = []
    for part_number, group in groups.items():
        if len(group) < 2:
            continue
        file_ids = sorted(s.file_id for s in group)
        findings.append(
            ReconciliationFinding(
                category=PdmReconciliationCategory.DUPLICATE_PART_NUMBER.value,
                severity=PdmReconciliationSeverity.ERROR.value,
                kind=None,
                item_id=None,
                file_id=None,
                part_number=part_number,
                revision=None,
                message=f"{len(group)} PDM files share part number {part_number!r}: "
                f"file ids {file_ids}",
                count=len(group),
            )
        )
    return findings


def find_orphaned_registry_entries(
    entries: Iterable[PartNumberRegistryEntry],
    *,
    live_made_part_numbers: frozenset[str],
    live_bought_part_numbers: frozenset[str],
) -> list[ReconciliationFinding]:
    """A registry entry no live item of its kind carries. Defensive, since
    the write path releases unused numbers."""
    findings: list[ReconciliationFinding] = []
    for entry in entries:
        live = live_made_part_numbers if entry.kind == "made" else live_bought_part_numbers
        if entry.part_number in live:
            continue
        findings.append(
            ReconciliationFinding(
                category=PdmReconciliationCategory.DUPLICATE_PART_NUMBER.value,
                severity=PdmReconciliationSeverity.INFO.value,
                kind=entry.kind,
                item_id=None,
                file_id=None,
                part_number=entry.part_number,
                revision=None,
                message="registry entry has no live item",
            )
        )
    return findings


def find_items_without_registry_entry(
    rows: Iterable[CadRowRef], registered_kind_by_part_number: Mapping[str, str]
) -> list[ReconciliationFinding]:
    """A CAD item whose part number the registry lacks or holds under the
    other kind."""
    findings: list[ReconciliationFinding] = []
    for row in rows:
        if not row.part_number:
            continue
        owner_kind = registered_kind_by_part_number.get(row.part_number)
        if owner_kind == row.kind:
            continue
        message = (
            "item has no registry entry"
            if owner_kind is None
            else f"registry entry for this part number is registered to {owner_kind!r}"
        )
        findings.append(
            ReconciliationFinding(
                category=PdmReconciliationCategory.DUPLICATE_PART_NUMBER.value,
                severity=PdmReconciliationSeverity.ERROR.value,
                kind=row.kind,
                item_id=row.item_id,
                file_id=row.pdm_file_id,
                part_number=row.part_number,
                revision=row.revision,
                message=message,
            )
        )
    return findings


def find_document_missing(
    links: Iterable[PdmDocumentLink], snapshots_by_key: Mapping[SnapshotKey, PdmFileSnapshot]
) -> list[ReconciliationFinding]:
    """A document link whose snapshot is missing or gone; the item file
    itself stays."""
    findings: list[ReconciliationFinding] = []
    for link in links:
        snapshot = snapshots_by_key.get((link.vault_id, link.file_id))
        if snapshot is not None and snapshot.sync_state != PdmFileSyncState.MISSING.value:
            continue
        reason = (
            "no snapshot found for the linked document"
            if snapshot is None
            else "linked document is missing"
        )
        findings.append(
            ReconciliationFinding(
                category=PdmReconciliationCategory.DOCUMENT_MISSING.value,
                severity=PdmReconciliationSeverity.WARNING.value,
                kind=link.kind.value,
                item_id=link.item_id,
                file_id=link.file_id,
                part_number=None,
                revision=None,
                message=reason,
            )
        )
    return findings


def find_document_unmatched(snapshots: Iterable[PdmFileSnapshot]) -> list[ReconciliationFinding]:
    """Documents never matched to an item, one finding per reason, without
    an age gate. An export waiting in a state documents are not synced from
    is not unmatched, it is simply not due yet."""
    groups: dict[str, int] = defaultdict(int)
    for snapshot in snapshots:
        if snapshot.kind != _DOCUMENT_KIND or snapshot.item_id is not None:
            continue
        if snapshot.sync_state not in (
            PdmFileSyncState.SKIPPED.value,
            PdmFileSyncState.ERROR.value,
        ):
            continue
        if snapshot.sync_state == PdmFileSyncState.SKIPPED.value and is_deliberate_skip(
            snapshot.last_error
        ):
            continue
        reason = snapshot.last_error or f"unmatched ({snapshot.sync_state.value})"
        groups[reason] += 1

    return [
        ReconciliationFinding(
            category=PdmReconciliationCategory.DOCUMENT_UNMATCHED.value,
            severity=PdmReconciliationSeverity.INFO.value,
            kind=_DOCUMENT_KIND,
            item_id=None,
            file_id=None,
            part_number=None,
            revision=None,
            message=reason,
            count=count,
        )
        for reason, count in groups.items()
    ]
