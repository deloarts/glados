"""
Shared archive/restore sequence for entities that toggle a boolean
`archived` flag: load the entity by id, raise a not-found error if it is
missing, let the caller run any entity-specific mutation through
`before_save` (guard checks against the entity's current, pre-flip state,
timestamp stamping, changelog entries, extra field changes), flip
`archived` to the target value, and persist. Idempotent by construction:
archiving an already-archived entity, or restoring an already-live one,
is not an error, it just re-runs `before_save` and re-saves.

Permission checks are the caller's responsibility and must run before
this helper is ever invoked, so an unauthorized caller cannot use a
missing id's error to learn whether that id exists. This module never
checks permissions, never logs, never publishes events, and never builds
the result DTO, only the fetch/guard/flip/persist sequence that is
identical across every archive/restore use case.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from typing import Protocol
from typing import TypeVar


class _Archivable(Protocol):
    archived: bool


TEntity = TypeVar("TEntity", bound=_Archivable)


async def set_archived(
    *,
    entity_id: int,
    archived: bool,
    load: Callable[[int], Awaitable[TEntity | None]],
    not_found: Callable[[int], Exception],
    save: Callable[[TEntity], Awaitable[TEntity]],
    before_save: Callable[[TEntity], Awaitable[None]] | None = None,
) -> TEntity:
    entity = await load(entity_id)
    if entity is None:
        raise not_found(entity_id)

    if before_save is not None:
        await before_save(entity)

    entity.archived = archived

    return await save(entity)
