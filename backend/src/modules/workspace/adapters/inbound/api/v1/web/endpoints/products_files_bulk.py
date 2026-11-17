"""
Batched read of Product file attachments, for views rendering many products
at once (the thumbnail column in the product management table) that would
otherwise issue one GET /products/{product_id}/files per row.

Routes (under /products-files):
  GET /: files for many products at once (url=None when storage disabled)

Deliberately its own prefix rather than a /products/files route:
products.router owns GET /products/{product_id} and is registered first, so a
flat /files path under that prefix would be swallowed by the int path param
and 422.

The query parameter stays `item_ids`, matching the other bulk file endpoints,
so one client-side files-store implementation serves every entity.
"""

from typing import Annotated

from fastapi import Depends
from fastapi import Query
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.domain.entities.user import User
from src.modules.workspace.adapters.inbound.api.deps.product_files import get_product_files_use_case
from src.modules.workspace.adapters.inbound.api.schemas.product_file_schema import (
    ProductFileResponse,
)
from src.modules.workspace.application.dto.product_file_dto import ProductFileResult
from src.modules.workspace.application.use_cases.product.get_product_files import GetProductFiles

router = APIRouter()


# Deliberately unpaginated: bounded per-item file attachments, and
# item_ids itself is already capped (max_length=200 below).
@router.get("/", response_model=list[ProductFileResponse])
async def list_files_for_items(
    item_ids: Annotated[list[int], Query(min_length=1, max_length=200)],
    _: User = Depends(get_current_active_user),
    use_case: GetProductFiles = Depends(get_product_files_use_case),
) -> list[ProductFileResult]:
    return await use_case.execute_many(item_ids=item_ids)
