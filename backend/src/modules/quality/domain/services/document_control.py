"""
The state changes of document control, one implementation for every kind of
controlled document (see entities/controlled_document.py). No I/O and no
permissions: each kind's rules decide who may do what, then call these to
do it the same way. Every change is also written to the document's
changelog.
"""

from dataclasses import replace
from datetime import datetime
from datetime import timedelta
from typing import TypeVar
from uuid import uuid4

from src.modules.platform.domain.entities.user import User
from src.modules.quality.domain.entities.controlled_document import ControlledDocument
from src.modules.quality.domain.errors import DocumentAlreadyInvalidError
from src.modules.quality.domain.errors import DocumentLockedError
from src.modules.quality.domain.errors import DocumentNotLockedError
from src.modules.quality.domain.errors import DocumentNotReleasedError
from src.modules.quality.domain.errors import ReleasedDocumentDeleteError
from src.shared_kernel.domain.services.changelog_service import append_changelog

# How long an edit lock lasts without activity. Editing renews it, so only an
# abandoned lock runs out.
LOCK_LEASE = timedelta(minutes=15)

D = TypeVar("D", bound=ControlledDocument)


def log(document: ControlledDocument, actor: User, now: datetime, text: str) -> None:
    document.changed = now
    document.changed_by_id = actor.id
    document.changed_by_full_name = actor.full_name
    document.changes = append_changelog(document.changes, actor.full_name, text)


# ── Edit lock ─────────────────────────────────────────────────────────


def assert_not_locked_by_other(
    document: ControlledDocument, actor: User, now: datetime, label: str
) -> None:
    """Refuses a change while someone else holds the edit lock. `label`
    names the document in the message, such as "Checklist #12"."""
    holder = document.lock_holder_id(now)
    if holder is not None and holder != actor.id:
        name = document.locked_by_full_name or f"user #{holder}"
        raise DocumentLockedError(
            f"{label} is being edited by {name} until "
            f"{document.lock_expires_at:%Y-%m-%d %H:%M} UTC at the latest."
        )


def assert_holds_lock(document: ControlledDocument, actor: User, now: datetime, label: str) -> None:
    """Refuses a save by anyone but the holder of the edit lock."""
    assert_not_locked_by_other(document, actor, now, label)
    if document.lock_holder_id(now) != actor.id:
        raise DocumentNotLockedError(
            f"{label} is not being edited by you; click Edit to take its lock before saving."
        )


def record_editor(document: ControlledDocument, actor: User) -> None:
    """Remembers who saved changes, so they hear about later revisions."""
    if actor.id != document.creator_id and actor.id not in document.editor_ids:
        document.editor_ids = [*document.editor_ids, actor.id]


def assert_deletable(document: ControlledDocument, label: str) -> None:
    if document.is_released:
        raise ReleasedDocumentDeleteError(
            f"{label} (revision {document.revision}) is released and kept as a record; "
            "mark it invalid instead."
        )


def take_lock(document: ControlledDocument, actor: User, now: datetime) -> int | None:
    """Gives `actor` the edit lock for another lease, or renews the lease
    they hold. Returns the id of the editor whose live lock this took over,
    or None; whether `actor` may take a lock over is the caller's to check."""
    holder = document.lock_holder_id(now)
    previous_name = document.locked_by_full_name or f"user #{holder}"
    if holder != actor.id:
        document.locked_at = now
    document.locked_by_id = actor.id
    document.locked_by_full_name = actor.full_name
    document.lock_expires_at = now + LOCK_LEASE
    if holder is None or holder == actor.id:
        return None
    document.changes = append_changelog(
        document.changes, actor.full_name, f"Took over editing from {previous_name}."
    )
    return holder


def renew_lock(document: ControlledDocument, actor: User, now: datetime) -> None:
    """Renews the lease of a lock `actor` holds, since a save is activity;
    without one nothing changes."""
    if document.lock_holder_id(now) == actor.id:
        document.lock_expires_at = now + LOCK_LEASE


def release_lock(document: ControlledDocument, actor: User, now: datetime) -> bool:
    """Ends the edit lock `actor` holds. False when they hold none, for
    instance because it ran out or was taken over."""
    if document.lock_holder_id(now) != actor.id:
        return False
    drop_lock(document)
    return True


def drop_lock(document: ControlledDocument) -> None:
    document.locked_by_id = None
    document.locked_at = None
    document.lock_expires_at = None
    document.locked_by_full_name = None


# ── Revisions ─────────────────────────────────────────────────────────


def start_revision(
    current: D, actor: User, now: datetime, *, revision: str, reason: str, takes_over_now: bool
) -> D:
    """Retires `current` as the latest revision and returns its successor,
    unsaved, as a draft by `actor` with the same content. `takes_over_now`
    supersedes `current` at once, for documents without a release step;
    otherwise it stays the valid revision until the new one is released.
    Save `current` first, so the lineage never has two latest revisions."""
    current.is_latest = False
    if takes_over_now:
        current.superseded_at = now
    drop_lock(current)
    log(current, actor, now, f"Revision {revision} started.")
    return replace(
        current,
        id=0,
        public_id=uuid4(),
        created=now,
        changed=now,
        changes=append_changelog(
            [],
            actor.full_name,
            f"Revision {revision} created from revision {current.revision}: {reason}",
        ),
        creator_id=actor.id,
        creator_full_name=actor.full_name,
        revision=revision,
        revision_reason=reason,
        editor_ids=[],
        is_latest=True,
        superseded_at=None,
        released_at=None,
        released_by_id=None,
        released_by_full_name=None,
        invalid_at=None,
        invalid_by_id=None,
        invalid_reason=None,
        invalid_by_full_name=None,
        locked_by_id=None,
        locked_at=None,
        lock_expires_at=None,
        locked_by_full_name=None,
    )


def restore_latest(previous: ControlledDocument, deleted: str, actor: User, now: datetime) -> None:
    """Makes `previous` the latest and valid revision again after the
    revision `deleted` that followed it was deleted."""
    previous.is_latest = True
    previous.superseded_at = None
    log(previous, actor, now, f"Latest revision again, revision {deleted} was deleted.")


# ── Release ───────────────────────────────────────────────────────────


def release(
    document: ControlledDocument,
    previous: ControlledDocument | None,
    actor: User,
    now: datetime,
) -> None:
    """Releases `document` and supersedes the revision before it."""
    if previous is not None and previous.superseded_at is None:
        previous.superseded_at = now
        log(previous, actor, now, f"Superseded by revision {document.revision}.")
    document.released_at = now
    document.released_by_id = actor.id
    document.released_by_full_name = actor.full_name
    drop_lock(document)
    log(document, actor, now, "Released.")


def assert_can_be_marked_invalid(document: ControlledDocument, label: str) -> None:
    if not document.is_released:
        raise DocumentNotReleasedError(
            f"{label} (revision {document.revision}) is not released; a draft is changed instead."
        )
    if document.is_invalid:
        raise DocumentAlreadyInvalidError(
            f"{label} (revision {document.revision}) is already marked invalid."
        )


def mark_invalid(document: ControlledDocument, actor: User, now: datetime, reason: str) -> None:
    """Marks a released revision invalid. It keeps its release, so what was
    signed off stays on record, and is corrected by a new revision."""
    document.invalid_at = now
    document.invalid_by_id = actor.id
    document.invalid_by_full_name = actor.full_name
    document.invalid_reason = reason
    log(document, actor, now, f"Marked invalid: {reason}")
