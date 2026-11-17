"""
Records who changed a row. Before every flush, each row of a model that
mixes in ChangedByColumns whose `changed` timestamp moved gets the acting
user of its session as `changed_by_id`.

The acting user is bound to the request's session by the auth dependencies
once they have verified the credential, never taken from the logging
context, whose user id is an unverified token claim. A session no request
bound, a worker's or a scheduled job's, has no acting user, so a change the
system makes on its own clears the changer instead of leaving the previous
person next to the newer timestamp.

The listener sits on the sync Session class behind SessionLocal, where ORM
session events live, and is attached in `session.py`, so every session the
app opens records changers, the test sessions included.
"""

from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import get_history

from src.modules.platform.adapters.outbound.persistence.models.changed_by_columns import (
    ChangedByColumns,
)

_ACTOR_KEY = "glados.acting_user_id"


def bind_acting_user(session: AsyncSession, user_id: int) -> None:
    """Makes `user_id` the changer of every row the session changes."""
    session.info[_ACTOR_KEY] = user_id


def _before_flush(session: Session, _flush_context: Any, _instances: Any) -> None:
    actor_id: int | None = session.info.get(_ACTOR_KEY)
    for obj in (*session.new, *session.dirty):
        if not isinstance(obj, ChangedByColumns) or getattr(obj, "changed", None) is None:
            continue
        if get_history(obj, "changed").has_changes():
            obj.changed_by_id = actor_id


def register_changer_tracking(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Attaches the listener to the sync Session class behind the factory."""
    sync_cls: type[Session] = session_factory.class_.sync_session_class
    if not event.contains(sync_cls, "before_flush", _before_flush):
        event.listen(sync_cls, "before_flush", _before_flush)
