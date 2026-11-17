"""
API key surface, read-only product access for hardware/machine clients.
"""

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.workspace.adapters.inbound.api.deps.products import get_product_by_number_use_case
from src.modules.workspace.adapters.inbound.api.deps.products import get_product_use_case
from src.modules.workspace.adapters.inbound.api.schemas.product_schema import ProductResponse
from src.modules.workspace.application.use_cases.product.get_product import GetProduct
from src.modules.workspace.application.use_cases.product.get_product import GetProductByNumber

router = APIRouter()


@router.get("/{product_id}", response_model=ProductResponse)
async def read_product_by_id(
    product_id: int,
    use_case: GetProduct = Depends(get_product_use_case),
) -> ProductResponse:
    result = await use_case.execute(product_id=product_id)
    return ProductResponse.model_validate(result.model_dump())


@router.get("/number/{product_number}", response_model=ProductResponse)
async def read_product_by_number(
    product_number: str,
    use_case: GetProductByNumber = Depends(get_product_by_number_use_case),
) -> ProductResponse:
    result = await use_case.execute(product_number=product_number)
    return ProductResponse.model_validate(result.model_dump())
