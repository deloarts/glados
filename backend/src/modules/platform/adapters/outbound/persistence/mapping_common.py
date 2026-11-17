"""Helpers many repository mappers share: the creator and changer pairs, the
change-tracking trio with `deleted` or `archived`, and the UTC re-attach
for datetime columns read back from SQLite.

They take plain values rather than the ORM row, because `Mapped[int]`
would not satisfy a Protocol declaring `int | None` under strict mypy.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from typing import Any
from typing import overload

from src.modules.platform.adapters.outbound.persistence.user_loading import user_orm_to_entity


@overload
def utc_aware(value: datetime) -> datetime: ...


@overload
def utc_aware(value: None) -> None: ...


@overload
def utc_aware(value: datetime | None) -> datetime | None: ...


def utc_aware(value: datetime | None) -> datetime | None:
    """Stamp UTC onto a naive datetime and return an aware one unchanged.

    SQLite, the test database, hands back naive datetimes even for a
    DateTime(timezone=True) column, while Postgres never does. Values are
    always stored as UTC, so the zone is attached rather than converted,
    and every entity carries an aware datetime regardless of dialect.
    """
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


def creator_kwargs(creator_id: int | None, creator: Any) -> dict[str, Any]:
    """The creator id and resolved User, for aggregates that expose one."""
    return {
        "creator_id": creator_id,
        "creator": user_orm_to_entity(creator) if creator else None,
    }


def changed_by_kwargs(changed_by_id: int | None, changed_by: Any) -> dict[str, Any]:
    """The changer id and resolved User, for aggregates that record one."""
    return {
        "changed_by_id": changed_by_id,
        "changed_by": user_orm_to_entity(changed_by) if changed_by else None,
    }


def soft_delete_kwargs(
    changed: date | None, changes: list[str] | None, deleted: bool
) -> dict[str, Any]:
    """The changed, changes and deleted fields."""
    return {"changed": changed, "changes": list(changes or []), "deleted": deleted}


def archived_kwargs(
    changed: date | None, changes: list[str] | None, archived: bool
) -> dict[str, Any]:
    """The changed, changes and archived fields."""
    return {"changed": changed, "changes": list(changes or []), "archived": archived}
