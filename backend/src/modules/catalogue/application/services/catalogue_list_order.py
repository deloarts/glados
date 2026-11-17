"""
Moves an entry of a hand-ordered catalogue list, such as the article groups
or the fabrication methods, one place up or down, or places it next to
another entry, which is what dragging a row does. The pickers of every
family offer the live entries in this order, so the ones used most can go
first. Every family shares the body; the use cases only pass their spec.
"""

from typing import Protocol

from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.shared_kernel.domain.services.list_order import ListEntry
from src.shared_kernel.domain.services.list_order import changed_sort_orders
from src.shared_kernel.domain.services.list_order import move_entry
from src.shared_kernel.domain.services.list_order import place_entry
from src.shared_kernel.domain.value_objects.list_move_direction import ListMoveDirection


class OrderedCatalogueRepo(Protocol):
    async def get_list_order(self) -> list[ListEntry]: ...

    async def set_sort_orders(self, sort_orders: dict[int, int], /) -> None: ...


class _UpdateRules(Protocol):
    @staticmethod
    def assert_can_update(actor: User) -> None: ...


class _OrderSpec(Protocol):
    @property
    def rules(self) -> type[_UpdateRules]: ...

    @property
    def not_found_error(self) -> type[Exception]: ...

    @property
    def label(self) -> str: ...


async def move_catalogue_entry(
    spec: _OrderSpec,
    repo: OrderedCatalogueRepo,
    actor: User,
    entry_id: int,
    direction: ListMoveDirection,
) -> None:
    """Moving needs the family's update right, the same as editing an entry."""
    spec.rules.assert_can_update(actor)
    entries = await repo.get_list_order()
    if not any(entry.id == entry_id for entry in entries):
        raise spec.not_found_error(f"{spec.label.capitalize()} #{entry_id} not found.")
    before = {entry.id: entry.sort_order for entry in entries}
    ordered = move_entry(entries, entry_id, direction)
    await repo.set_sort_orders(changed_sort_orders(before, ordered))
    log.info(f"Moved {spec.label} ID={entry_id} {direction.value}.")


async def place_catalogue_entry(
    spec: _OrderSpec,
    repo: OrderedCatalogueRepo,
    actor: User,
    entry_id: int,
    *,
    after_id: int | None,
    before_id: int | None,
) -> None:
    """Puts the entry directly after `after_id`, or before `before_id`.
    Needs the family's update right, the same as a move."""
    spec.rules.assert_can_update(actor)
    entries = await repo.get_list_order()
    known = {entry.id for entry in entries}
    for wanted in (entry_id, after_id, before_id):
        if wanted is not None and wanted not in known:
            raise spec.not_found_error(f"{spec.label.capitalize()} #{wanted} not found.")
    before = {entry.id: entry.sort_order for entry in entries}
    ordered = place_entry(entries, entry_id, after_id=after_id, before_id=before_id)
    await repo.set_sort_orders(changed_sort_orders(before, ordered))
    log.info(f"Placed {spec.label} ID={entry_id} after {after_id} / before {before_id}.")
