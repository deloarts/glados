"""
Creates a made item demand through the creation the demand families share
(_demand_family/create_demand.py). A made item demand adds its alteration
link, checked before the item is read, and the made item it alters must
exist. Its default delivery date is the project's required delivery date
for made items.
"""

from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.errors import MadeItemNotFoundError
from src.modules.catalogue.domain.events.made_item_events import MadeItemDemandItemCreated
from src.modules.catalogue.domain.policies.made_item_rules import MadeItemCatalogueRules
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.catalogue.ports.outbound.catalogue_queries import IMadeItemQueries
from src.modules.fulfillment.application.dto.made_item_demand_dto import CreateMadeItemDemandCommand
from src.modules.fulfillment.application.dto.made_item_demand_dto import MadeItemDemandItemResult
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases._demand_family.create_demand import CreateDemand
from src.modules.fulfillment.application.use_cases.made_item_demand._spec import SPEC
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.services.made_item_demand_rules import MadeItemDemandRules
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemDemandItemRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.domain.entities.project import Project
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries
from src.shared_kernel.domain.events.base import DomainEvent
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class CreateDemandItem(
    CreateDemand[
        MadeItemDemandItem, MadeItem, CreateMadeItemDemandCommand, MadeItemDemandItemResult
    ]
):
    _spec = SPEC
    _demand_rules = MadeItemDemandRules

    def __init__(
        self,
        demand_repo: IMadeItemDemandItemRepository,
        made_item_repo: IMadeItemQueries,
        project_repo: IProjectQueries,
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
    ) -> None:
        super().__init__(
            demand_repo,
            made_item_repo,
            project_repo,
            event_bus=event_bus,
            uow=uow,
            reconciler=reconciler,
        )

    async def _demandable_item(self, cmd: CreateMadeItemDemandCommand) -> MadeItem:
        MadeItemDemandRules.assert_valid_alteration(
            cmd.made_item_id, cmd.is_alteration, cmd.alteration_of_made_item_id
        )
        item = found_or_raise(
            await self._items.get_by_id(cmd.made_item_id),
            MadeItemNotFoundError,
            f"Catalogue item #{cmd.made_item_id} not found.",
        )
        MadeItemCatalogueRules.assert_item_demandable(item)

        if cmd.alteration_of_made_item_id is not None:
            alteration_source = await self._items.get_by_id(cmd.alteration_of_made_item_id)
            if not alteration_source:
                raise MadeItemNotFoundError(
                    f"Catalogue item #{cmd.alteration_of_made_item_id} not found."
                )
        return item

    def _new_demand(
        self, actor: User, cmd: CreateMadeItemDemandCommand, item: MadeItem, project: Project
    ) -> MadeItemDemandItem:
        now = now_utc()
        return MadeItemDemandItem(
            id=0,
            created=now,
            changed=now,
            changes=append_changelog([], actor.full_name, "Demand item created."),
            status=MadeItemDemandStatus.default(),
            quantity=cmd.quantity,
            unit=cmd.unit,
            items_per_unit=cmd.items_per_unit,
            high_priority=cmd.high_priority,
            notify_on_delivery=cmd.notify_on_delivery,
            note=cmd.note,
            desired_delivery_date=(
                cmd.desired_delivery_date
                if "desired_delivery_date" in cmd.model_fields_set
                else project.required_delivery_date_made
            ),
            creator_id=actor.id,
            made_item_id=item.id,
            project_id=project.id,
            creator=actor,
            item_part_number=item.part_number or "",
            item_article_name=item.article_name,
            project_number=project.project_number,
            project_customer=project.customer.name if project.customer else "",
            project_description=project.description or "",
            project_status=project.status,
            is_alteration=cmd.is_alteration,
            alteration_of_made_item_id=cmd.alteration_of_made_item_id,
        )

    def _created_event(self, demand: MadeItemDemandItem) -> DomainEvent:
        return MadeItemDemandItemCreated(
            demand_id=demand.id,
            made_item_id=demand.made_item_id,
            project_id=demand.project_id,
            creator_id=demand.creator_id,
        )
