"""
PAT surface, read-only product access.
"""

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_user_pat
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.user import User
from src.modules.workspace.adapters.inbound.api.deps.products import get_product_by_number_use_case
from src.modules.workspace.adapters.inbound.api.deps.products import get_product_use_case
from src.modules.workspace.adapters.inbound.api.deps.products import get_products_use_case
from src.modules.workspace.adapters.inbound.api.schemas.product_schema import ProductFilterParams
from src.modules.workspace.adapters.inbound.api.schemas.product_schema import ProductResponse
from src.modules.workspace.application.use_cases.product.get_product import GetProduct
from src.modules.workspace.application.use_cases.product.get_product import GetProductByNumber
from src.modules.workspace.application.use_cases.product.get_product import GetProducts

router = APIRouter()


@router.get("/", response_model=PageResponse[ProductResponse])
async def read_products(
    params: ProductFilterParams = Depends(),
    _: User = Depends(get_current_user_pat),
    use_case: GetProducts = Depends(get_products_use_case),
) -> PageResponse[ProductResponse]:
    result = await use_case.execute(params.to_dto())
    return PageResponse.from_result(result, params, item_model=ProductResponse)


@router.get("/{product_id}", response_model=ProductResponse)
async def read_product_by_id(
    product_id: int,
    _: User = Depends(get_current_user_pat),
    use_case: GetProduct = Depends(get_product_use_case),
) -> ProductResponse:
    result = await use_case.execute(product_id=product_id)
    return ProductResponse.model_validate(result.model_dump())


@router.get("/number/{product_number}", response_model=ProductResponse)
async def read_product_by_number(
    product_number: str,
    _: User = Depends(get_current_user_pat),
    use_case: GetProductByNumber = Depends(get_product_by_number_use_case),
) -> ProductResponse:
    result = await use_case.execute(product_number=product_number)
    return ProductResponse.model_validate(result.model_dump())
