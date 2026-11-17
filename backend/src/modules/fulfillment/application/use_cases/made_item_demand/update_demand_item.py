"""
Edits a made item demand through the edit the demand families share
(_demand_family/update_demand.py). A made item demand adds its alteration
link: whether it is an alteration and of which made item, which must exist.
"""

from src.modules.catalogue.domain.errors import MadeItemNotFoundError
from src.modules.catalogue.ports.outbound.catalogue_queries import IMadeItemQueries
from src.modules.fulfillment.application.dto.made_item_demand_dto import MadeItemDemandItemResult
from src.modules.fulfillment.application.dto.made_item_demand_dto import UpdateMadeItemDemandCommand
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases._demand_family.update_demand import UpdateDemand
from src.modules.fulfillment.application.use_cases.made_item_demand._spec import SPEC
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.services.made_item_demand_rules import MadeItemDemandRules
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemDemandItemRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class UpdateDemandItem(
    UpdateDemand[MadeItemDemandItem, UpdateMadeItemDemandCommand, MadeItemDemandItemResult]
):
    _spec = SPEC
    _demand_rules = MadeItemDemandRules

    def __init__(
        self,
        demand_repo: IMadeItemDemandItemRepository,
        made_item_repo: IMadeItemQueries,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        allocation_repo: IMadeItemAllocationRepository | None = None,
    ) -> None:
        super().__init__(
            demand_repo, uow=uow, reconciler=reconciler, allocation_repo=allocation_repo
        )
        self._items = made_item_repo

    async def _check(self, demand: MadeItemDemandItem, cmd: UpdateMadeItemDemandCommand) -> None:
        MadeItemDemandRules.assert_valid_alteration(
            demand.made_item_id, cmd.is_alteration, cmd.alteration_of_made_item_id
        )
        if cmd.alteration_of_made_item_id is not None:
            alteration_source = await self._items.get_by_id(cmd.alteration_of_made_item_id)
            if not alteration_source:
                raise MadeItemNotFoundError(
                    f"Catalogue item #{cmd.alteration_of_made_item_id} not found."
                )

    def _apply_extra(self, demand: MadeItemDemandItem, cmd: UpdateMadeItemDemandCommand) -> None:
        demand.is_alteration = cmd.is_alteration
        demand.alteration_of_made_item_id = cmd.alteration_of_made_item_id
