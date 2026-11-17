"""Converts the document control fields of an entity to result fields."""

from typing import Any

from src.modules.quality.domain.entities.controlled_document import ControlledDocument
from src.shared_kernel.domain.services.clock import now_utc


def document_result_fields(entity: ControlledDocument) -> dict[str, Any]:
    """The ControlledDocumentResult fields of `entity`. A lock that has run
    out is left out, so readers see only who edits the document now."""
    locked = entity.lock_holder_id(now_utc()) is not None
    return {
        "id": entity.id,
        "public_id": entity.public_id,
        "created": entity.created,
        "changed": entity.changed,
        "changed_by_id": entity.changed_by_id,
        "changed_by_full_name": entity.changed_by_full_name,
        "creator_id": entity.creator_id,
        "creator_full_name": entity.creator_full_name,
        "document_number": entity.document_number,
        "lineage": entity.lineage,
        "revision": entity.revision,
        "revision_reason": entity.revision_reason,
        "is_latest": entity.is_latest,
        "superseded_at": entity.superseded_at,
        "read_only": entity.read_only,
        "released_at": entity.released_at,
        "released_by_id": entity.released_by_id,
        "released_by_full_name": entity.released_by_full_name,
        "invalid_at": entity.invalid_at,
        "invalid_by_id": entity.invalid_by_id,
        "invalid_by_full_name": entity.invalid_by_full_name,
        "invalid_reason": entity.invalid_reason,
        "locked_by_id": entity.locked_by_id if locked else None,
        "locked_by_full_name": entity.locked_by_full_name if locked else None,
        "locked_at": entity.locked_at if locked else None,
        "lock_expires_at": entity.lock_expires_at if locked else None,
    }
