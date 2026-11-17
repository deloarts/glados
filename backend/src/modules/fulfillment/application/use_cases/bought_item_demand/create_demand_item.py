"""
Creates a bought item demand through the creation the demand families share
(_demand_family/create_demand.py). Its default delivery date is the
project's required delivery date for bought items.
"""

from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.errors import BoughtItemNotFoundError
from src.modules.catalogue.domain.events.bought_item_events import DemandItemCreated
from src.modules.catalogue.domain.policies.bought_item_rules import BoughtItemCatalogueRules
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.fulfillment.application.dto.bought_item_demand_dto import CreateDemandItemCommand
from src.modules.fulfillment.application.dto.bought_item_demand_dto import DemandItemResult
from src.modules.fulfillment.application.use_cases._demand_family.create_demand import CreateDemand
from src.modules.fulfillment.application.use_cases.bought_item_demand._demand_spec import SPEC
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.services.bought_item_demand_rules import BoughtItemDemandRules
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.workspace.domain.entities.project import Project
from src.shared_kernel.domain.events.base import DomainEvent
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class CreateDemandItem(
    CreateDemand[BoughtItemDemandItem, BoughtItem, CreateDemandItemCommand, DemandItemResult]
):
    _spec = SPEC
    _demand_rules = BoughtItemDemandRules

    async def _demandable_item(self, cmd: CreateDemandItemCommand) -> BoughtItem:
        item = found_or_raise(
            await self._items.get_by_id(cmd.item_id),
            BoughtItemNotFoundError,
            f"Catalogue item #{cmd.item_id} not found.",
        )
        BoughtItemCatalogueRules.assert_item_demandable(item)
        return item

    def _new_demand(
        self, actor: User, cmd: CreateDemandItemCommand, item: BoughtItem, project: Project
    ) -> BoughtItemDemandItem:
        now = now_utc()
        return BoughtItemDemandItem(
            id=0,
            created=now,
            changed=now,
            changes=append_changelog([], actor.full_name, "Demand item created."),
            status=BoughtItemDemandStatus.default(),
            quantity=cmd.quantity,
            unit=cmd.unit,
            items_per_unit=cmd.items_per_unit,
            high_priority=cmd.high_priority,
            notify_on_delivery=cmd.notify_on_delivery,
            note=cmd.note,
            desired_delivery_date=(
                cmd.desired_delivery_date
                if "desired_delivery_date" in cmd.model_fields_set
                else project.required_delivery_date_bought
            ),
            creator_id=actor.id,
            item_id=item.id,
            project_id=project.id,
            creator=actor,
            item_order_code_1=item.order_code_1,
            item_article_name=item.article_name,
            project_number=project.project_number,
            project_customer=project.customer.name if project.customer else "",
            project_description=project.description or "",
            project_status=project.status,
        )

    def _created_event(self, demand: BoughtItemDemandItem) -> DomainEvent:
        return DemandItemCreated(
            demand_id=demand.id,
            item_id=demand.item_id,
            project_id=demand.project_id,
            creator_id=demand.creator_id,
        )
