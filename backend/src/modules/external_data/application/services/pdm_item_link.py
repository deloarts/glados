"""
Sets the PDM sync state shown on a linked made or bought item, shared by
the poller, the trigger path and the settings save so the three mark an
item the same way. Does not commit; the caller owns the transaction.
"""

from src.modules.catalogue.domain.value_objects.pdm_sync_state import PdmSyncState
from src.modules.catalogue.ports.outbound.cad_item_store_port import IBoughtItemCadStore
from src.modules.catalogue.ports.outbound.cad_item_store_port import IMadeItemCadStore


async def set_item_pdm_sync_state(
    made_items: IMadeItemCadStore,
    bought_items: IBoughtItemCadStore,
    kind: str,
    item_id: int,
    state: PdmSyncState,
) -> None:
    """Stores `state` on the item `kind` and `item_id` name. A missing item
    is left alone, since its link is what the caller is reporting on."""
    if kind == "made":
        item = await made_items.get_by_id(item_id)
        if item is not None:
            item.pdm_sync_state = state
            await made_items.save(item)
    else:
        bought = await bought_items.get_by_id(item_id)
        if bought is not None:
            bought.pdm_sync_state = state
            await bought_items.save(bought)
