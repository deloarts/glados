"""
The read side of the made-item revision family. The read side provides
the newest key, unparseable revision handling as a null next_revision
plus message, and permission gates that decide whether "New revision" is
offered. Any active user may call this, same as other reads: it never
mutates anything, and `can_create`/`reason` merely describe what a
subsequent POST …/revisions would do, they never enforce it.

`_build_revisions_result` is shared with
`get_made_item_revisions_by_part_number.py` (the PAT-only,
part-number-keyed variant, same newest-first ordering) so the two never
drift apart on the next_revision/can_create/reason logic; only the
lookup key differs between them.
"""

from src.modules.catalogue.application.dto.made_item_dto import MadeItemRevisionsResult
from src.modules.catalogue.application.dto.made_item_dto import MadeItemRevisionSummary
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.errors import MadeItemNotFoundError
from src.modules.catalogue.domain.errors import RevisionNotIncrementableError
from src.modules.catalogue.domain.policies import revision_scheme
from src.modules.catalogue.domain.policies.made_item_rules import newest_of
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.ports.outbound.catalogue_settings_repository import (
    ICatalogueSettingsRepository,
)
from src.modules.catalogue.ports.outbound.repositories.made_item_repository import (
    IMadeItemRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission


async def _build_revisions_result(
    siblings: list[MadeItem],
    reference_item: MadeItem,
    actor: User,
    admin_settings_repo: ICatalogueSettingsRepository,
    *,
    reverse: bool,
) -> MadeItemRevisionsResult:
    """`reference_item` is whichever item the caller actually looked up
    (by id, or the family's newest for the part-number lookup); its
    `data_source` drives the "cad" reason, matching
    CreateMadeItemRevision's own gate. `newest` (below) is only ever used
    to compute `next_revision` and flag `is_newest`."""
    newest = newest_of(siblings)
    ordered = sorted(
        siblings,
        key=lambda i: (revision_scheme.sort_key(i.revision), i.created, i.id),
        reverse=reverse,
    )

    made_item_settings = await admin_settings_repo.get_made_items()
    try:
        next_revision: str | None = revision_scheme.next_revision(
            newest.revision, made_item_settings.revision_skip_ambiguous_letters
        )
        next_revision_error: str | None = None
    except RevisionNotIncrementableError as exc:
        next_revision = None
        next_revision_error = str(exc)

    # Order matches CreateMadeItemRevision's own gate order (assert_can_
    # update, then the CAD check): a user without write:made_items
    # would hit that gate first, so "no_write" takes priority over
    # "cad" when both apply.
    reason: str | None
    if not actor.has_permission(Permission.WRITE_MADE_ITEMS):
        reason = "no_write"
    elif reference_item.data_source == DataSource.CAD.value:
        reason = "cad"
    else:
        reason = None

    can_create = reason is None and next_revision_error is None

    return MadeItemRevisionsResult(
        items=[
            MadeItemRevisionSummary(
                id=sibling.id,
                public_id=sibling.public_id,
                revision=sibling.revision,
                revision_date=sibling.revision_date,
                status=sibling.status,
                successor_item_id=sibling.successor_item_id,
                created=sibling.created,
                is_newest=sibling.id == newest.id,
            )
            for sibling in ordered
        ],
        next_revision=next_revision,
        next_revision_error=next_revision_error,
        can_create=can_create,
        reason=reason,
    )


class GetMadeItemRevisions:
    def __init__(
        self, made_item_repo: IMadeItemRepository, admin_settings_repo: ICatalogueSettingsRepository
    ) -> None:
        self._items = made_item_repo
        self._admin_settings = admin_settings_repo

    async def execute(self, actor: User, item_id: int) -> MadeItemRevisionsResult:
        item = found_or_raise(
            await self._items.get_by_id(item_id),
            MadeItemNotFoundError,
            f"Catalogue item #{item_id} not found.",
        )

        siblings: list[MadeItem] = (
            await self._items.get_revisions(item.part_number)
            if item.part_number is not None
            else [item]
        )
        return await _build_revisions_result(
            siblings, item, actor, self._admin_settings, reverse=True
        )
