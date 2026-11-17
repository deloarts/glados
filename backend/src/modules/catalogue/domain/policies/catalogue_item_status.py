"""Status and successor of a catalogue item, and which items new work may name.

A made, bought or source item's status is the user's intent, active, inactive
or replaced, with nothing to derive it from. Only a replaced item names a
successor, the item of the same catalogue that takes its place, and moving an
item to replaced needs one. STATUS_MOVES lists every status move with what it
does to the successor, and assert_catalogue_status_change applies it to one
write. The status flips of PDM ingest, which map a file's workflow state onto
the status of its CAD row, follow their own rules and are not checked here;
the items ingest creates and the revisions it makes go through the same use
cases as the web and are checked.

demandable_refusal tells whether new work may name an item: a new demand,
lot, order line or substitute needs an item that is active, not archived and
whose PDM file is not missing. merge_target_verdict tells whether an item
may take the merge of another one.
"""

from dataclasses import dataclass
from enum import Enum

from src.modules.catalogue.domain.errors import CatalogueStatusChangeError
from src.modules.catalogue.domain.errors import CatalogueSuccessorNotFoundError
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.pdm_sync_state import PdmSyncState
from src.modules.catalogue.domain.value_objects.source_item_status import SourceItemCatalogueStatus

# The status of an item of any of the three catalogues, which share their
# values.
type CatalogueItemStatus = (
    MadeItemCatalogueStatus | BoughtItemCatalogueStatus | SourceItemCatalogueStatus
)

# The statuses the three catalogues share.
ACTIVE = "active"
INACTIVE = "inactive"
REPLACED = "replaced"


class SuccessorEffect(Enum):
    """What a status move does to the item's successor."""

    REQUIRED = "required"
    CLEARED = "cleared"


@dataclass(frozen=True)
class StatusMove:
    """One move of a catalogue item's status. `from_status` is None for an
    item being created."""

    from_status: str | None
    to_status: str
    successor: SuccessorEffect

    @property
    def effect(self) -> str:
        if self.successor is SuccessorEffect.REQUIRED:
            return "names a successor that exists, is not archived and does not lead back"
        return "names no successor; a stored one is dropped"


STATUS_MOVES: tuple[StatusMove, ...] = (
    StatusMove(None, ACTIVE, SuccessorEffect.CLEARED),
    StatusMove(None, INACTIVE, SuccessorEffect.CLEARED),
    StatusMove(None, REPLACED, SuccessorEffect.REQUIRED),
    StatusMove(ACTIVE, INACTIVE, SuccessorEffect.CLEARED),
    StatusMove(ACTIVE, REPLACED, SuccessorEffect.REQUIRED),
    StatusMove(INACTIVE, ACTIVE, SuccessorEffect.CLEARED),
    StatusMove(INACTIVE, REPLACED, SuccessorEffect.REQUIRED),
    StatusMove(REPLACED, ACTIVE, SuccessorEffect.CLEARED),
    StatusMove(REPLACED, INACTIVE, SuccessorEffect.CLEARED),
)


@dataclass(frozen=True, kw_only=True)
class CatalogueStatusChange:
    """One write of a catalogue item's status and successor.

    `family` names the catalogue in messages, for example "bought item".
    `item_id`, `old_status` and `old_successor_id` are None for an item being
    created. `status_owned_by_pdm` is true on a CAD row while PDM ownership
    is enforced: PDM sets that status and leaves a replaced row without a
    successor, so a user may also clear the successor of such a row.
    """

    family: str
    item_id: int | None
    old_status: CatalogueItemStatus | None
    old_successor_id: int | None
    new_status: CatalogueItemStatus
    requested_successor_id: int | None
    status_owned_by_pdm: bool = False


@dataclass(frozen=True, kw_only=True)
class SuccessorFacts:
    """The successor a write names, as stored: whether it is archived, and
    the successors that follow it, nearest first."""

    id: int
    archived: bool
    chain: tuple[int, ...] = ()


def successor_to_check(change: CatalogueStatusChange) -> int | None:
    """The successor the write has to prove valid, None when the write names
    none or keeps the one it already had."""
    if change.new_status != REPLACED or change.requested_successor_id is None:
        return None
    if _unchanged(change):
        return None
    return change.requested_successor_id


def assert_catalogue_status_change(
    change: CatalogueStatusChange, successor: SuccessorFacts | None
) -> int | None:
    """Raises when the write leaves status and successor inconsistent, and
    returns the successor the item names afterwards. `successor` describes
    the successor successor_to_check names, None when it does not exist.

    A write that changes neither status nor successor is left alone, so an
    inconsistent row stays editable. A status move follows
    STATUS_MOVES: a move to replaced needs a valid successor, every other
    move drops a stored successor and refuses a new one. Within one status, a
    replaced item may point at another valid successor and may drop its
    successor only where PDM owns its status; an active or inactive item may
    drop a successor but not take one.
    """
    if _unchanged(change):
        return change.old_successor_id
    if change.new_status == change.old_status:
        return _within_status(change, successor)
    move = _move(change)
    if move.successor is SuccessorEffect.CLEARED:
        _refuse_new_successor(change)
        return None
    return _valid_successor(change, successor)


def assert_new_item_status(*, family: str, status: CatalogueItemStatus) -> None:
    """Applies the status moves of a new item, which names no successor when
    it is created: it starts active or inactive, never replaced."""
    assert_catalogue_status_change(
        CatalogueStatusChange(
            family=family,
            item_id=None,
            old_status=None,
            old_successor_id=None,
            new_status=status,
            requested_successor_id=None,
        ),
        None,
    )


def demandable_refusal(
    *, status: CatalogueItemStatus, archived: bool, pdm_sync_state: PdmSyncState | None = None
) -> str | None:
    """Why new work may not name an item, None when it may. New work is a
    new demand, lot, order line or substitute. Work that already names the
    item is not affected by its status."""
    if archived:
        return "is archived"
    if status != ACTIVE:
        return f"is {status.value}"
    if pdm_sync_state == PdmSyncState.MISSING:
        return "is missing in PDM"
    return None


class MergeTargetRefusal(Enum):
    """Why an item may not take a merge."""

    ARCHIVED = "archived"
    NOT_ACTIVE = "not_active"


@dataclass(frozen=True)
class MergeTargetVerdict:
    """Whether an item may take the merge of another one. `refusal` is None
    when it may; `reactivates` is true when the merge makes the target
    active again."""

    refusal: MergeTargetRefusal | None
    reactivates: bool


def merge_target_verdict(
    *, archived: bool, status: CatalogueItemStatus, successor_item_id: int | None, source_id: int
) -> MergeTargetVerdict:
    """Judges a target for the merge of the item `source_id`. The merge
    moves live demands and order lines onto the target, so it must be active
    and not archived. The one exception is a target the source had replaced:
    the merge undoes the replacement and makes the target active again."""
    if archived:
        return MergeTargetVerdict(MergeTargetRefusal.ARCHIVED, reactivates=False)
    if status == ACTIVE:
        return MergeTargetVerdict(None, reactivates=False)
    if status == REPLACED and successor_item_id == source_id:
        return MergeTargetVerdict(None, reactivates=True)
    return MergeTargetVerdict(MergeTargetRefusal.NOT_ACTIVE, reactivates=False)


def _unchanged(change: CatalogueStatusChange) -> bool:
    return (
        change.new_status == change.old_status
        and change.requested_successor_id == change.old_successor_id
    )


def _subject(change: CatalogueStatusChange) -> str:
    if change.item_id is None:
        return f"A new {change.family}"
    return f"{change.family.capitalize()} #{change.item_id}"


def _move(change: CatalogueStatusChange) -> StatusMove:
    for move in STATUS_MOVES:
        if move.from_status == change.old_status and move.to_status == change.new_status:
            return move
    old = change.old_status.value if change.old_status is not None else None
    raise CatalogueStatusChangeError(
        f"{_subject(change)} cannot move from {old} to {change.new_status.value}."
    )


def _within_status(change: CatalogueStatusChange, successor: SuccessorFacts | None) -> int | None:
    if change.new_status != REPLACED:
        _refuse_new_successor(change)
        return None
    if change.requested_successor_id is None:
        if change.status_owned_by_pdm:
            return None
        raise CatalogueStatusChangeError(
            f"{_subject(change)} is replaced and keeps a successor; make it active or "
            "inactive to drop the successor."
        )
    return _valid_successor(change, successor)


def _refuse_new_successor(change: CatalogueStatusChange) -> None:
    requested = change.requested_successor_id
    if requested is not None and requested != change.old_successor_id:
        raise CatalogueStatusChangeError(
            f"{_subject(change)} is {change.new_status.value} and cannot name successor "
            f"#{requested}; "
            "only a replaced item names a successor."
        )


def _valid_successor(change: CatalogueStatusChange, successor: SuccessorFacts | None) -> int:
    requested = change.requested_successor_id
    if requested is None:
        raise CatalogueStatusChangeError(f"{_subject(change)} needs a successor to be replaced.")
    if successor is None:
        raise CatalogueSuccessorNotFoundError(f"Successor {change.family} #{requested} not found.")
    if requested == change.item_id:
        raise CatalogueStatusChangeError(f"{_subject(change)} cannot be its own successor.")
    if change.item_id is not None and change.item_id in successor.chain:
        raise CatalogueStatusChangeError(
            f"Successor {change.family} #{requested} leads back to {change.family} "
            f"#{change.item_id}; successors cannot form a loop."
        )
    if successor.archived:
        raise CatalogueStatusChangeError(
            f"Successor {change.family} #{requested} is archived; a replaced item needs a "
            "successor that is not archived."
        )
    return requested
