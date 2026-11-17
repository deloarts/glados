"""
File attachment endpoints for BoughtItem catalogue records.

Routes (all under /bought-items/{item_id}/files):
  GET    /                  - list files (url=None when storage disabled)
  POST   /                  - upload file (multipart; requires storage)
  GET    /{file_id}         - download file bytes (same gate as list)
  PATCH  /{file_id}         - rename file (metadata only, no storage required)
  DELETE /{file_id}         - delete file and storage object
"""

from src.modules.catalogue.adapters.inbound.api.deps.items import get_bought_item_files_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_delete_bought_item_file_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_download_bought_item_file_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_update_bought_item_file_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_upload_bought_item_file_use_case,
)
from src.modules.catalogue.adapters.inbound.api.schemas.bought_item_file_schema import (
    BoughtItemFileResponse,
)
from src.modules.catalogue.adapters.inbound.api.schemas.bought_item_file_schema import (
    BoughtItemFileUpdateRequest,
)
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints._item_file_router import (
    ItemFileEndpointConfig,
)
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints._item_file_router import (
    build_item_file_router,
)
from src.modules.catalogue.application.dto.bought_item_file_dto import UpdateBoughtItemFileCommand
from src.modules.catalogue.domain.value_objects.bought_item_file_category import (
    BoughtItemFileCategory,
)

router = build_item_file_router(
    ItemFileEndpointConfig(
        response_model=BoughtItemFileResponse,
        update_request_model=BoughtItemFileUpdateRequest,
        update_command=UpdateBoughtItemFileCommand,
        category_enum=BoughtItemFileCategory,
        list_dep=get_bought_item_files_use_case,
        download_dep=get_download_bought_item_file_use_case,
        upload_dep=get_upload_bought_item_file_use_case,
        update_dep=get_update_bought_item_file_use_case,
        delete_dep=get_delete_bought_item_file_use_case,
    )
)
