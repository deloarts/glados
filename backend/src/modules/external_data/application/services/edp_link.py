"""
Links a bought item to an EPLAN Data Portal part: stores edp_part_id and
edp_synced_at without touching any other field, so it is allowed on a PDM
row too (edp_part_id is dual-owned, edp_synced_at Glados-owned), writes a
changelog line when the link changes, and requests the item's picture.
Shared by the import, the lookup on an item and PDM ingest, which reads the
part id from the file's datacard. Does not commit; the caller's unit of
work does.
"""

from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.errors import BoughtItemNotFoundError
from src.modules.catalogue.domain.events.bought_item_events import BoughtItemEdpPictureRequested
from src.modules.catalogue.ports.outbound.cad_item_store_port import IBoughtItemCadStore
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


def stamp_edp_link(item: BoughtItem, author_name: str, edp_part_id: int | None) -> None:
    """Sets or clears the item's portal link in memory and logs a change of
    it. The caller saves the item and requests the picture of a link."""
    now = now_utc()
    if item.edp_part_id != edp_part_id:
        note = (
            f"Linked to EPLAN Data Portal part #{edp_part_id}."
            if edp_part_id is not None
            else f"Unlinked from EPLAN Data Portal part #{item.edp_part_id}."
        )
        item.changes = append_changelog(item.changes, author_name, note)
    item.edp_part_id = edp_part_id
    item.edp_synced_at = now if edp_part_id is not None else None
    item.changed = now


async def link_edp_part(
    items: IBoughtItemCadStore,
    bus: IEventBus,
    actor: User,
    item_id: int,
    edp_part_id: int,
) -> BoughtItem:
    item = await items.get_by_id(item_id)
    if item is None:
        raise BoughtItemNotFoundError(f"Catalogue item #{item_id} not found.")
    stamp_edp_link(item, actor.full_name, edp_part_id)
    saved = await items.save(item)
    await bus.publish(BoughtItemEdpPictureRequested(item_id=saved.id))
    return saved
