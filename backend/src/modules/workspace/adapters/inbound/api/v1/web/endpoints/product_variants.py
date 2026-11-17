"""
Endpoints for a product's variants, mounted under /products. The list is
read and saved as a whole; a variant left out of a save is archived.
"""

from fastapi import Depends
from fastapi import Query
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.domain.entities.user import User
from src.modules.workspace.adapters.inbound.api.deps.product_variants import (
    get_product_variants_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.product_variants import (
    get_save_product_variants_use_case,
)
from src.modules.workspace.adapters.inbound.api.schemas.product_variant_schema import (
    ProductVariantResponse,
)
from src.modules.workspace.adapters.inbound.api.schemas.product_variant_schema import (
    ProductVariantsSaveRequest,
)
from src.modules.workspace.application.dto.product_variant_dto import SaveProductVariantsCommand
from src.modules.workspace.application.use_cases.product_variant.variants import GetProductVariants
from src.modules.workspace.application.use_cases.product_variant.variants import SaveProductVariants

router = APIRouter()


@router.get("/{product_id}/variants", response_model=list[ProductVariantResponse])
async def read_product_variants(
    product_id: int,
    include_archived: bool = Query(default=False),
    _: User = Depends(get_current_active_user),
    use_case: GetProductVariants = Depends(get_product_variants_use_case),
) -> list[ProductVariantResponse]:
    results = await use_case.execute(product_id, include_archived)
    return [ProductVariantResponse.model_validate(r.model_dump()) for r in results]


@router.put("/{product_id}/variants", response_model=list[ProductVariantResponse])
async def save_product_variants(
    product_id: int,
    body: ProductVariantsSaveRequest,
    actor: User = Depends(get_current_active_user),
    use_case: SaveProductVariants = Depends(get_save_product_variants_use_case),
) -> list[ProductVariantResponse]:
    results = await use_case.execute(
        actor, product_id, SaveProductVariantsCommand(**body.model_dump())
    )
    return [ProductVariantResponse.model_validate(r.model_dump()) for r in results]
