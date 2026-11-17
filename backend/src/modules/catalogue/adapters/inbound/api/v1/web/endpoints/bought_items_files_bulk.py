"""
Batched read of BoughtItem file attachments, for views rendering many items
at once (thumbnail columns in the catalogue/demand/order tables) that would
otherwise issue one GET /bought-items/{item_id}/files per row.

Routes (under /bought-items-files):
  GET /: files for many items at once (url=None when storage disabled)

Deliberately its own prefix rather than a /bought-items/files route:
bought_items.router owns GET /bought-items/{item_id} and is registered first,
so a flat /files path under that prefix would be swallowed by the int
path param and 422.
"""

from src.modules.catalogue.adapters.inbound.api.deps.items import get_bought_item_files_use_case
from src.modules.catalogue.adapters.inbound.api.schemas.bought_item_file_schema import (
    BoughtItemFileResponse,
)
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints._item_file_router import (
    ItemFileBulkEndpointConfig,
)
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints._item_file_router import (
    build_bulk_item_file_router,
)

router = build_bulk_item_file_router(
    ItemFileBulkEndpointConfig(
        response_model=BoughtItemFileResponse,
        list_dep=get_bought_item_files_use_case,
    )
)
