"""
Places a machine pool next to another pool by dragging, in the hand-kept
order the pool lists and pickers show. Needs the right to edit pools, the
same as an edit.
"""

from src.modules.fulfillment.domain.errors import MachinePoolNotFoundError
from src.modules.fulfillment.domain.services.machine_pool_rules import MachinePoolRules
from src.modules.fulfillment.ports.outbound.repositories.machine_pool_repository import (
    IMachinePoolRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.list_order import changed_sort_orders
from src.shared_kernel.domain.services.list_order import place_entry


class PlaceMachinePool:
    def __init__(self, machine_pool_repo: IMachinePoolRepository, *, uow: IUnitOfWork) -> None:
        self._pools = machine_pool_repo
        self._uow = uow

    async def execute(
        self, actor: User, pool_id: int, *, after_id: int | None, before_id: int | None
    ) -> None:
        """Puts the pool directly after `after_id`, or before `before_id`."""
        MachinePoolRules.assert_can_update(actor)
        entries = await self._pools.get_list_order()
        known = {entry.id for entry in entries}
        for wanted in (pool_id, after_id, before_id):
            if wanted is not None and wanted not in known:
                raise MachinePoolNotFoundError(f"Machine pool #{wanted} not found.")
        before = {entry.id: entry.sort_order for entry in entries}
        ordered = place_entry(entries, pool_id, after_id=after_id, before_id=before_id)
        await self._pools.set_sort_orders(changed_sort_orders(before, ordered))
        await self._uow.commit()
        log.info(f"Placed machine pool ID={pool_id} after {after_id} / before {before_id}.")
