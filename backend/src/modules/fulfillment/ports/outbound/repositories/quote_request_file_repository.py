"""
Repository interfaces for the documents of a supplier's offer on a quote
request, and the supplier entry they belong to.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.fulfillment.domain.entities.quote_request import QuoteRequestSupplier
from src.modules.fulfillment.domain.entities.quote_request_file import QuoteRequestFile
from src.modules.fulfillment.domain.value_objects.quote_file_category import QuoteFileCategory


@runtime_checkable
class IQuoteRequestFileRepository(Protocol):
    async def get_by_id(self, id: int) -> QuoteRequestFile | None: ...
    async def get_by_item_id(self, item_id: int) -> list[QuoteRequestFile]: ...
    async def get_by_item_ids(self, item_ids: list[int]) -> list[QuoteRequestFile]: ...
    async def get_by_item_id_and_category(
        self, item_id: int, category: QuoteFileCategory
    ) -> list[QuoteRequestFile]: ...
    async def save(self, file: QuoteRequestFile) -> QuoteRequestFile: ...
    async def delete(self, file: QuoteRequestFile) -> None: ...


@runtime_checkable
class IQuoteRequestSupplierRepository(Protocol):
    """The supplier entries of quote requests, looked up on their own as the
    owners of offer documents."""

    async def get_by_id(self, id: int) -> QuoteRequestSupplier | None: ...
