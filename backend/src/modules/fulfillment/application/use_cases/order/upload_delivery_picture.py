"""
Uploads a picture taken at goods receipt, such as a photo of damaged goods
or of the stamped delivery note, as an order file of the PICTURE category
that names the delivery row it documents. It is the receiver's evidence for
a claim against the supplier or the carrier, so it needs the permission to
receive deliveries rather than the one to edit orders, and it is listed with
the order's other files.

The delivery row must belong to the order line, and the line to the order;
otherwise the row is not found. Any row of the line takes a picture, a
correction that rejected pieces after receipt as well, so the damage found
later is documented on the row that records it.
"""

from typing import Any

from src.modules.fulfillment.application.dto.order_file_dto import OrderFileResult
from src.modules.fulfillment.application.use_cases.order._lines import read_order_line
from src.modules.fulfillment.application.use_cases.order.upload_order_file import UploadOrderFile
from src.modules.fulfillment.domain.entities.order_file import OrderFile
from src.modules.fulfillment.domain.errors import OrderItemDeliveryNotFoundError
from src.modules.fulfillment.domain.errors import OrderNotFoundError
from src.modules.fulfillment.domain.services.order_rules import OrderRules
from src.modules.fulfillment.domain.value_objects.order_file_category import OrderFileCategory
from src.modules.fulfillment.ports.outbound.repositories.order_file_repository import (
    IOrderFileRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemDeliveryRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import StorageNotEnabledError
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class _DeliveryPictureUpload(UploadOrderFile):
    """The order file upload with the receiver's permission, whose stored
    row names `delivery_id`."""

    def __init__(
        self,
        order_repo: IOrderRepository,
        file_repo: IOrderFileRepository,
        storage: IStoragePort | None,
        *,
        uow: IUnitOfWork,
        delivery_id: int,
    ) -> None:
        super().__init__(order_repo, file_repo, storage, uow=uow)
        self._delivery_id = delivery_id

    async def _load_writable_item(self, actor: User, item_id: int) -> Any:
        OrderRules.assert_can_receive_delivery(actor)
        if self._storage is None:
            raise StorageNotEnabledError("Storage is not enabled.")
        order = await self._item_repo.get_by_id(item_id)
        if not order:
            raise OrderNotFoundError(f"Order #{item_id} not found.")
        return order

    async def _store_blob(
        self,
        actor: User,
        item_id: int,
        data: bytes,
        file_name: str,
        content_type: str,
        category: Any,
    ) -> OrderFile:
        record = await super()._store_blob(actor, item_id, data, file_name, content_type, category)
        record.delivery_id = self._delivery_id
        return record


class UploadDeliveryPicture:
    """Stores one picture of a delivery row; see the module docstring."""

    def __init__(
        self,
        order_repo: IOrderRepository,
        order_item_repo: IOrderItemRepository,
        delivery_repo: IOrderItemDeliveryRepository,
        file_repo: IOrderFileRepository,
        storage: IStoragePort | None,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._orders = order_repo
        self._order_items = order_item_repo
        self._deliveries = delivery_repo
        self._files = file_repo
        self._storage = storage
        self._uow = uow

    async def execute(
        self,
        actor: User,
        order_id: int,
        order_item_id: int,
        delivery_id: int,
        data: bytes,
        file_name: str,
        content_type: str,
    ) -> OrderFileResult:
        OrderRules.assert_can_receive_delivery(actor)
        await read_order_line(self._orders, self._order_items, order_id, order_item_id)
        rows = await self._deliveries.get_by_order_item_id(order_item_id)
        if not any(row.id == delivery_id for row in rows):
            raise OrderItemDeliveryNotFoundError(
                f"Delivery #{delivery_id} not found on order item #{order_item_id}."
            )
        upload = _DeliveryPictureUpload(
            self._orders, self._files, self._storage, uow=self._uow, delivery_id=delivery_id
        )
        return await upload.execute(
            actor, order_id, data, file_name, content_type, OrderFileCategory.PICTURE
        )
