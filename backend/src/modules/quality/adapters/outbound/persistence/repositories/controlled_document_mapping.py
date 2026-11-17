"""
Maps the document control columns (models/controlled_document_columns.py)
to the fields of ControlledDocument and back, and holds the queries every
repository of a controlled document runs the same way.
"""

from typing import Any

from sqlalchemy import desc
from sqlalchemy import func
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel
from src.modules.platform.adapters.outbound.persistence.user_loading import load_user
from src.modules.quality.domain.entities.controlled_document import ControlledDocument


def user_load_options(model: Any) -> tuple[ORMOption, ...]:
    """Loads the users the document control fields name."""
    return tuple(
        load_user(getattr(model, name))
        for name in ("creator", "changed_by", "released_by", "invalid_by", "locked_by")
    )


def lineage_order(model: Any) -> tuple[Any, ...]:
    """Newest revision first, the order revision_scheme.sort_key gives: a
    longer revision string is newer, then plain string order."""
    return (desc(func.length(model.revision)), desc(model.revision))


def _name(user: UserOrmModel | None) -> str | None:
    return user.full_name if user else None


def document_fields(orm: Any) -> dict[str, Any]:
    """The ControlledDocument keyword arguments of a loaded row."""
    created = utc_aware(orm.created)
    assert created is not None  # non-null column
    return {
        "id": orm.id,
        "public_id": orm.public_id,
        "created": created,
        "changed": utc_aware(orm.changed),
        "changed_by_id": orm.changed_by_id,
        "changes": list(orm.changes or []),
        "creator_id": orm.creator_id,
        "document_number": orm.document_number,
        "lineage": orm.lineage,
        "revision": orm.revision,
        "revision_reason": orm.revision_reason,
        "is_latest": orm.is_latest,
        "superseded_at": utc_aware(orm.superseded_at),
        "released_at": utc_aware(orm.released_at),
        "released_by_id": orm.released_by_id,
        "invalid_at": utc_aware(orm.invalid_at),
        "invalid_by_id": orm.invalid_by_id,
        "invalid_reason": orm.invalid_reason,
        "locked_by_id": orm.locked_by_id,
        "locked_at": utc_aware(orm.locked_at),
        "lock_expires_at": utc_aware(orm.lock_expires_at),
        "editor_ids": [int(i) for i in (orm.editor_ids or [])],
        "creator_full_name": _name(orm.creator) or "",
        "changed_by_full_name": _name(orm.changed_by),
        "released_by_full_name": _name(orm.released_by),
        "invalid_by_full_name": _name(orm.invalid_by),
        "locked_by_full_name": _name(orm.locked_by),
    }


def document_values(item: ControlledDocument) -> dict[str, Any]:
    """The column values of the document control fields, for insert and update."""
    return {
        "created": item.created,
        "changed": item.changed,
        "changed_by_id": item.changed_by_id,
        "changes": item.changes,
        "creator_id": item.creator_id,
        "document_number": item.document_number,
        "lineage": item.lineage,
        "revision": item.revision,
        "revision_reason": item.revision_reason,
        "is_latest": item.is_latest,
        "superseded_at": item.superseded_at,
        "released_at": item.released_at,
        "released_by_id": item.released_by_id,
        "invalid_at": item.invalid_at,
        "invalid_by_id": item.invalid_by_id,
        "invalid_reason": item.invalid_reason,
        "locked_by_id": item.locked_by_id,
        "locked_at": item.locked_at,
        "lock_expires_at": item.lock_expires_at,
        "editor_ids": list(item.editor_ids),
    }
