"""Moves a production machine one place up or down, or places it next to
another machine by dragging, in the hand-kept order the machine lists, the
schedule board and the pickers show. Both need the right to edit machines,
the same as an edit."""

from src.modules.catalogue.domain.errors import ProductionMachineNotFoundError
from src.modules.fulfillment.domain.services.production_machine_rules import ProductionMachineRules
from src.modules.fulfillment.ports.outbound.repositories.production_machine_repository import (
    IProductionMachineRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.list_order import changed_sort_orders
from src.shared_kernel.domain.services.list_order import move_entry
from src.shared_kernel.domain.services.list_order import place_entry
from src.shared_kernel.domain.value_objects.list_move_direction import ListMoveDirection


class MoveProductionMachine:
    def __init__(self, machine_repo: IProductionMachineRepository, *, uow: IUnitOfWork) -> None:
        self._machines = machine_repo
        self._uow = uow

    async def execute(self, actor: User, machine_id: int, direction: ListMoveDirection) -> None:
        ProductionMachineRules.assert_can_update(actor)
        entries = await self._machines.get_list_order()
        if not any(entry.id == machine_id for entry in entries):
            raise ProductionMachineNotFoundError(f"Production machine #{machine_id} not found.")
        before = {entry.id: entry.sort_order for entry in entries}
        ordered = move_entry(entries, machine_id, direction)
        await self._machines.set_sort_orders(changed_sort_orders(before, ordered))
        await self._uow.commit()
        log.info(f"Moved production machine ID={machine_id} {direction.value}.")


class PlaceProductionMachine:
    def __init__(self, machine_repo: IProductionMachineRepository, *, uow: IUnitOfWork) -> None:
        self._machines = machine_repo
        self._uow = uow

    async def execute(
        self, actor: User, machine_id: int, *, after_id: int | None, before_id: int | None
    ) -> None:
        """Puts the machine directly after `after_id`, or before `before_id`."""
        ProductionMachineRules.assert_can_update(actor)
        entries = await self._machines.get_list_order()
        known = {entry.id for entry in entries}
        for wanted in (machine_id, after_id, before_id):
            if wanted is not None and wanted not in known:
                raise ProductionMachineNotFoundError(f"Production machine #{wanted} not found.")
        before = {entry.id: entry.sort_order for entry in entries}
        ordered = place_entry(entries, machine_id, after_id=after_id, before_id=before_id)
        await self._machines.set_sort_orders(changed_sort_orders(before, ordered))
        await self._uow.commit()
        log.info(
            f"Placed production machine ID={machine_id} after {after_id} / before {before_id}."
        )
