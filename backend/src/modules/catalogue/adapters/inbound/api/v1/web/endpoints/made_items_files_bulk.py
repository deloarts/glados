"""
Batched read of MadeItem file attachments, for views rendering many items
at once (thumbnail columns in the catalogue/demand/lot tables) that would
otherwise issue one GET /made-items/{item_id}/files per row.

Routes (under /made-items-files):
  GET /, files for many items at once (url=None when storage disabled)

Deliberately its own prefix rather than a /made-items/files route:
made_items.router owns GET /made-items/{item_id} and is registered first,
so a flat /files path under that prefix would be swallowed by the int
path param and 422.
"""

from src.modules.catalogue.adapters.inbound.api.deps.items import get_made_item_files_use_case
from src.modules.catalogue.adapters.inbound.api.schemas.made_item_file_schema import (
    MadeItemFileResponse,
)
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints._item_file_router import (
    ItemFileBulkEndpointConfig,
)
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints._item_file_router import (
    build_bulk_item_file_router,
)

router = build_bulk_item_file_router(
    ItemFileBulkEndpointConfig(
        response_model=MadeItemFileResponse,
        list_dep=get_made_item_files_use_case,
    )
)
