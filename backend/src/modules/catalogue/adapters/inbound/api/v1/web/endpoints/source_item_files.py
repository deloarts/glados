"""
File attachment endpoints for SourceItem catalogue records.

Routes (all under /source-items/{item_id}/files):
  GET    /                  - list files (url=None when storage disabled)
  POST   /                  - upload file (multipart; requires storage)
  GET    /{file_id}         - download file bytes (same gate as list)
  PATCH  /{file_id}         - rename file (metadata only, no storage required)
  DELETE /{file_id}         - delete file and storage object
"""

from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_delete_source_item_file_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_download_source_item_file_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.items import get_source_item_files_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_update_source_item_file_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_upload_source_item_file_use_case,
)
from src.modules.catalogue.adapters.inbound.api.schemas.source_item_file_schema import (
    SourceItemFileResponse,
)
from src.modules.catalogue.adapters.inbound.api.schemas.source_item_file_schema import (
    SourceItemFileUpdateRequest,
)
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints._item_file_router import (
    ItemFileEndpointConfig,
)
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints._item_file_router import (
    build_item_file_router,
)
from src.modules.catalogue.application.dto.source_item_file_dto import UpdateSourceItemFileCommand
from src.modules.catalogue.domain.value_objects.source_item_file_category import (
    SourceItemFileCategory,
)

router = build_item_file_router(
    ItemFileEndpointConfig(
        response_model=SourceItemFileResponse,
        update_request_model=SourceItemFileUpdateRequest,
        update_command=UpdateSourceItemFileCommand,
        category_enum=SourceItemFileCategory,
        list_dep=get_source_item_files_use_case,
        download_dep=get_download_source_item_file_use_case,
        upload_dep=get_upload_source_item_file_use_case,
        update_dep=get_update_source_item_file_use_case,
        delete_dep=get_delete_source_item_file_use_case,
    )
)
