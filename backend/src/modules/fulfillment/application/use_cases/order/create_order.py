"""
Creates a new order for a supplier, generating the next order number from the configured
format, and publishing an OrderCreated event.
"""

from src.modules.fulfillment.application.dto.order_dto import CreateOrderCommand
from src.modules.fulfillment.application.dto.order_dto import OrderResult
from src.modules.fulfillment.application.mappers.order_mapper import OrderMapper
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.events.order_events import OrderCreated
from src.modules.fulfillment.domain.services.order_rules import OrderRules
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class CreateOrder:
    def __init__(
        self,
        order_repo: IOrderRepository,
        *,
        event_bus: IEventBus,
        admin_settings_repo: IFulfillmentSettingsRepository,
        uow: IUnitOfWork,
    ) -> None:
        self._orders = order_repo
        self._bus = event_bus
        self._admin_settings = admin_settings_repo
        self._uow = uow

    async def execute(self, actor: User, cmd: CreateOrderCommand) -> OrderResult:
        OrderRules.assert_can_create(actor)
        saved = await self.add(actor, cmd)
        await self._uow.commit()

        log.info(f"Created order {saved.order_number!r}, ID={saved.id}.")
        return OrderMapper.to_result(saved)

    async def add(self, actor: User, cmd: CreateOrderCommand) -> Order:
        """Saves a new DRAFT order and stages its OrderCreated event, without
        committing, for a caller that books more in the same transaction. The
        order number is drawn here, so such a caller takes its lifecycle
        locks first."""
        now = now_utc()
        template = (await self._admin_settings.get_orders()).order_number_format
        order_number = await self._orders.next_order_number(template)

        order = Order(
            id=0,
            order_number=order_number,
            created=now,
            changed=now,
            changes=append_changelog([], actor.full_name, f"Order {order_number} created."),
            status=OrderStatus.default(),
            note=cmd.note,
            ordered_date=None,
            expected_delivery_date=None,
            delivery_date=None,
            storage_place=None,
            creator_id=actor.id,
            supplier_id=cmd.supplier_id,
            creator=actor,
        )

        saved = await self._orders.save(order)

        await self._bus.publish(
            OrderCreated(
                order_id=saved.id,
                order_number=saved.order_number,
                creator_id=saved.creator_id,
                supplier_id=saved.supplier_id,
            )
        )
        return saved
