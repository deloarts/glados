"""
Moves a product family one place up or down, or places it next to another
family by dragging, in the hand-kept order its pickers offer. See
catalogue_list_order.py for the shared logic.
"""

from src.modules.catalogue.application.services.catalogue_list_order import move_catalogue_entry
from src.modules.catalogue.application.services.catalogue_list_order import place_catalogue_entry
from src.modules.catalogue.application.use_cases.product_family._spec import SPEC
from src.modules.catalogue.ports.outbound.repositories.product_family_repository import (
    IProductFamilyRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.value_objects.list_move_direction import ListMoveDirection


class MoveProductFamily:
    def __init__(self, product_family_repo: IProductFamilyRepository, *, uow: IUnitOfWork) -> None:
        self._repo = product_family_repo
        self._uow = uow

    async def execute(self, actor: User, entry_id: int, direction: ListMoveDirection) -> None:
        await move_catalogue_entry(SPEC, self._repo, actor, entry_id, direction)
        await self._uow.commit()


class PlaceProductFamily:
    def __init__(self, product_family_repo: IProductFamilyRepository, *, uow: IUnitOfWork) -> None:
        self._repo = product_family_repo
        self._uow = uow

    async def execute(
        self, actor: User, entry_id: int, *, after_id: int | None, before_id: int | None
    ) -> None:
        await place_catalogue_entry(
            SPEC, self._repo, actor, entry_id, after_id=after_id, before_id=before_id
        )
        await self._uow.commit()
