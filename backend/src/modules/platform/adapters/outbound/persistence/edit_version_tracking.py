"""
Moves the edit version of master data rows. Before every flush, each changed
row of a model that mixes in EditVersionColumn gets the edit version it was
loaded with plus one, so a client that read the row before the write and
sends that version back with its edit is refused with 409.

A row counts as changed when a column or a many-to-many collection, such as
its article groups, holds a value other than the one it was loaded with. The change timestamp, the changelog, the
changer and the columns the model lists in `__edit_version_ignored__` do not
count, so a save that changes nothing, or a sync that only stamps its own
bookkeeping, leaves the version alone. A repository that saves rows of a
child table as part of the row's edit, such as the components of a product
device, moves the version itself with `bump_edit_version_by_hand` when only
those rows changed.

The listener sees ORM writes only. A Core UPDATE of such a table that
changes a field an edit form sends moves `edit_version` in its own SET
clause.

It is attached in `session.py` next to the changer tracking, so every
session the app opens moves edit versions, the test sessions included.
"""

from datetime import UTC
from datetime import datetime
from typing import Any

from sqlalchemy import event
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import Mapper
from sqlalchemy.orm import PassiveFlag
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import History
from sqlalchemy.orm.attributes import get_history

from src.modules.platform.adapters.outbound.persistence.models.edit_version_column import (
    EditVersionColumn,
)

_EDIT_VERSION = "edit_version"
# Written by writes that change no field as well.
_ALWAYS_IGNORED = frozenset({_EDIT_VERSION, "changed", "changes", "changed_by_id", "changed_by"})


def _tracked_keys(mapper: Mapper[Any], ignored: frozenset[str]) -> list[str]:
    """The row's own columns and its many-to-many collections. A many-to-one
    reference is written through its foreign key column, and a one-to-many
    collection holds other rows, which a write elsewhere can touch through a
    back reference."""
    keys = [prop.key for prop in mapper.column_attrs]
    keys += [rel.key for rel in mapper.relationships if rel.secondary is not None]
    return [key for key in keys if key not in ignored]


def _as_utc(value: Any) -> Any:
    """SQLite hands a datetime back naive while the entity writes it aware,
    so the two compare unequal although they are the same instant."""
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _changed(history: History) -> bool:
    if not history.has_changes():
        return False
    if len(history.added) == 1 and len(history.deleted) == 1:
        return bool(_as_utc(history.added[0]) != _as_utc(history.deleted[0]))
    return True


def _has_field_changes(obj: EditVersionColumn) -> bool:
    ignored = _ALWAYS_IGNORED | type(obj).__edit_version_ignored__
    return any(
        _changed(get_history(obj, key, passive=PassiveFlag.PASSIVE_NO_INITIALIZE))
        for key in _tracked_keys(inspect(obj, raiseerr=True).mapper, ignored)
    )


def _loaded_edit_version(obj: EditVersionColumn) -> int:
    """The version the row holds in the database, even when a caller set the
    attribute already."""
    history = get_history(obj, _EDIT_VERSION)
    if history.deleted:
        return int(history.deleted[0] or 0)
    return int(obj.edit_version or 0)


def bump_edit_version_by_hand(obj: EditVersionColumn) -> None:
    """Moves the version of a loaded row whose own columns may not change,
    once per flush: the listener counts from the same loaded version."""
    obj.edit_version = _loaded_edit_version(obj) + 1


def _before_flush(session: Session, _flush_context: Any, _instances: Any) -> None:
    for obj in session.dirty:
        if not isinstance(obj, EditVersionColumn) or obj in session.deleted:
            continue
        if _has_field_changes(obj):
            obj.edit_version = _loaded_edit_version(obj) + 1


def register_edit_version_tracking(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Attaches the listener to the sync Session class behind the factory."""
    sync_cls: type[Session] = session_factory.class_.sync_session_class
    if not event.contains(sync_cls, "before_flush", _before_flush):
        event.listen(sync_cls, "before_flush", _before_flush)
