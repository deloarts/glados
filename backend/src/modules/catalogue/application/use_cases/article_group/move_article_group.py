"""
Moves an article group one place up or down, or places it next to another
group by dragging, in the hand-kept order its pickers offer. See
catalogue_list_order.py for the shared logic.
"""

from src.modules.catalogue.application.services.catalogue_list_order import move_catalogue_entry
from src.modules.catalogue.application.services.catalogue_list_order import place_catalogue_entry
from src.modules.catalogue.application.use_cases.article_group._spec import SPEC
from src.modules.catalogue.ports.outbound.repositories.article_group_repository import (
    IArticleGroupRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.value_objects.list_move_direction import ListMoveDirection


class MoveArticleGroup:
    def __init__(self, article_group_repo: IArticleGroupRepository, *, uow: IUnitOfWork) -> None:
        self._repo = article_group_repo
        self._uow = uow

    async def execute(self, actor: User, entry_id: int, direction: ListMoveDirection) -> None:
        await move_catalogue_entry(SPEC, self._repo, actor, entry_id, direction)
        await self._uow.commit()


class PlaceArticleGroup:
    def __init__(self, article_group_repo: IArticleGroupRepository, *, uow: IUnitOfWork) -> None:
        self._repo = article_group_repo
        self._uow = uow

    async def execute(
        self, actor: User, entry_id: int, *, after_id: int | None, before_id: int | None
    ) -> None:
        await place_catalogue_entry(
            SPEC, self._repo, actor, entry_id, after_id=after_id, before_id=before_id
        )
        await self._uow.commit()
