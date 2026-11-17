"""
File attachment endpoints for MadeItem catalogue records.

Routes (all under /made-items/{item_id}/files):
  GET    /                  - list files (url=None when storage disabled)
  POST   /                  - upload file (multipart; requires storage)
  GET    /{file_id}         - download file bytes (same gate as list)
  PATCH  /{file_id}         - rename file (metadata only, no storage required)
  DELETE /{file_id}         - delete file and storage object
"""

from src.modules.catalogue.adapters.inbound.api.deps.items import get_delete_made_item_file_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_download_made_item_file_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.items import get_made_item_files_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_update_made_item_file_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_upload_made_item_file_use_case
from src.modules.catalogue.adapters.inbound.api.schemas.made_item_file_schema import (
    MadeItemFileResponse,
)
from src.modules.catalogue.adapters.inbound.api.schemas.made_item_file_schema import (
    MadeItemFileUpdateRequest,
)
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints._item_file_router import (
    ItemFileEndpointConfig,
)
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints._item_file_router import (
    build_item_file_router,
)
from src.modules.catalogue.application.dto.made_item_file_dto import UpdateMadeItemFileCommand
from src.modules.catalogue.domain.value_objects.made_item_file_category import MadeItemFileCategory

router = build_item_file_router(
    ItemFileEndpointConfig(
        response_model=MadeItemFileResponse,
        update_request_model=MadeItemFileUpdateRequest,
        update_command=UpdateMadeItemFileCommand,
        category_enum=MadeItemFileCategory,
        list_dep=get_made_item_files_use_case,
        download_dep=get_download_made_item_file_use_case,
        upload_dep=get_upload_made_item_file_use_case,
        update_dep=get_update_made_item_file_use_case,
        delete_dep=get_delete_made_item_file_use_case,
    )
)
