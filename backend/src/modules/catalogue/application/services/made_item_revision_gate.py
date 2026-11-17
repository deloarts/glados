"""
Thin application-layer glue for domain.services.made_item_rules.
assert_editable: resolves a made item's revision siblings and the
revision_only_newest_editable setting, then calls the pure domain check.
Shared by every process/file mutation use case (create/update/delete/
reorder/regroup process, upload/update/delete file) so each does not
re-derive the same two repository calls; none of them change `status`, so
the unconditional (no status exemption) shape of assert_editable applies
everywhere it is used.
"""

from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.policies.made_item_rules import assert_editable
from src.modules.catalogue.ports.outbound.catalogue_settings_repository import (
    ICatalogueSettingsRepository,
)
from src.modules.catalogue.ports.outbound.repositories.made_item_repository import (
    IMadeItemRepository,
)


async def assert_made_item_editable(
    item: MadeItem,
    made_item_repo: IMadeItemRepository,
    admin_settings_repo: ICatalogueSettingsRepository,
) -> None:
    """Raises MadeItemNotNewestRevisionError (409) when `item` is not the
    newest revision of its part-number family and
    admin_made_item_settings.revision_only_newest_editable is on. A NULL
    part_number is always exempt (no family to be non-newest in)."""
    if item.part_number is None:
        return
    settings = await admin_settings_repo.get_made_items()
    siblings = await made_item_repo.get_revisions(item.part_number)
    assert_editable(item, siblings, settings.revision_only_newest_editable)
