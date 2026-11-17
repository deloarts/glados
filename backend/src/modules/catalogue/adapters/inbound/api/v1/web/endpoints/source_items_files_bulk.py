"""
Batched read of SourceItem file attachments, for views rendering many items
at once (thumbnail columns in the catalogue and demand tables) that would
otherwise issue one GET /source-items/{item_id}/files per row.

Routes (under /source-items-files):
  GET /: files for many items at once (url=None when storage disabled)

Deliberately its own prefix rather than a /source-items/files route:
source_items.router owns GET /source-items/{item_id} and is registered first,
so a flat /files path under that prefix would be swallowed by the int
path param and 422.
"""

from src.modules.catalogue.adapters.inbound.api.deps.items import get_source_item_files_use_case
from src.modules.catalogue.adapters.inbound.api.schemas.source_item_file_schema import (
    SourceItemFileResponse,
)
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints._item_file_router import (
    ItemFileBulkEndpointConfig,
)
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints._item_file_router import (
    build_bulk_item_file_router,
)

router = build_bulk_item_file_router(
    ItemFileBulkEndpointConfig(
        response_model=SourceItemFileResponse,
        list_dep=get_source_item_files_use_case,
    )
)
