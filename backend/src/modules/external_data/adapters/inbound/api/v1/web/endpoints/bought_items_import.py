"""
The bought-item batch create: validate spreadsheet rows, then create the
ready ones. Both need the bought item create permission.
"""

from fastapi import Depends
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.external_data.adapters.inbound.api.deps.items import (
    get_commit_batch_bought_items_use_case,
)
from src.modules.external_data.adapters.inbound.api.deps.items import (
    get_validate_batch_bought_items_use_case,
)
from src.modules.external_data.adapters.inbound.api.schemas.bought_item_import_schema import (
    BatchBoughtItemsRequest,
)
from src.modules.external_data.adapters.inbound.api.schemas.bought_item_import_schema import (
    CommitBatchBoughtItemsResponse,
)
from src.modules.external_data.adapters.inbound.api.schemas.bought_item_import_schema import (
    ValidateBatchBoughtItemsResponse,
)
from src.modules.external_data.application.dto.bought_item_import_dto import BatchBoughtItemRowInput
from src.modules.external_data.application.dto.bought_item_import_dto import (
    CommitBatchBoughtItemsResult,
)
from src.modules.external_data.application.dto.bought_item_import_dto import (
    ValidateBatchBoughtItemsResult,
)
from src.modules.external_data.application.use_cases.bought_item_import.batch_create_items import (
    CommitBatchBoughtItemRows,
)
from src.modules.external_data.application.use_cases.bought_item_import.batch_create_items import (
    ValidateBatchBoughtItemRows,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.post("/validate", response_model=ValidateBatchBoughtItemsResponse)
async def validate_batch_bought_items(
    body: BatchBoughtItemsRequest,
    actor: User = Depends(get_current_active_user),
    use_case: ValidateBatchBoughtItemRows = Depends(get_validate_batch_bought_items_use_case),
) -> ValidateBatchBoughtItemsResult:
    rows = [BatchBoughtItemRowInput(**row.model_dump()) for row in body.rows]
    return await use_case.execute(actor=actor, rows=rows, lookup=body.lookup)


@router.post(
    "/commit", response_model=CommitBatchBoughtItemsResponse, status_code=status.HTTP_201_CREATED
)
async def commit_batch_bought_items(
    body: BatchBoughtItemsRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CommitBatchBoughtItemRows = Depends(get_commit_batch_bought_items_use_case),
) -> CommitBatchBoughtItemsResult:
    """Creates the rows that validate as ready and, with the lookup, links
    the existing items to their portal part, in one transaction. Rows not in
    handled_row_indexes were left alone."""
    rows = [BatchBoughtItemRowInput(**row.model_dump()) for row in body.rows]
    return await use_case.execute(actor=actor, rows=rows, lookup=body.lookup)
