"""
Lists the files attached to an order on the shared item-file core. File
metadata is returned even when storage is disabled, with `url` set to None.
"""

from src.modules.fulfillment.application.dto.order_file_dto import OrderFileResult
from src.modules.fulfillment.application.use_cases.order._file_kind import ORDER_FILE_KIND
from src.modules.fulfillment.domain.entities.order_file import OrderFile
from src.modules.fulfillment.ports.outbound.repositories.order_file_repository import (
    IOrderFileRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository
from src.modules.platform.application.services.file_attachments.base import GetItemFilesBase
from src.modules.platform.ports.outbound.storage_port import IStoragePort


class GetOrderFiles(GetItemFilesBase[OrderFile, OrderFileResult]):
    _kind = ORDER_FILE_KIND

    def __init__(
        self,
        order_repo: IOrderRepository,
        file_repo: IOrderFileRepository,
        storage: IStoragePort | None,
    ) -> None:
        super().__init__(order_repo, file_repo, storage)

    async def execute(self, order_id: int) -> list[OrderFileResult]:
        return await super().execute(order_id)
