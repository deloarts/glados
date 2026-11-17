"""
Product family endpoints, manages the manufacturer product families
referenced by bought items.
"""

from datetime import tzinfo

from fastapi import Depends
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_archive_product_family_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.items import get_create_product_family_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_move_product_family_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_place_product_family_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_product_families_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_product_family_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_restore_product_family_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.items import get_update_product_family_use_case
from src.modules.catalogue.adapters.inbound.api.schemas.product_family_schema import (
    ProductFamilyCreateRequest,
)
from src.modules.catalogue.adapters.inbound.api.schemas.product_family_schema import (
    ProductFamilyFilterParams,
)
from src.modules.catalogue.adapters.inbound.api.schemas.product_family_schema import (
    ProductFamilyResponse,
)
from src.modules.catalogue.adapters.inbound.api.schemas.product_family_schema import (
    ProductFamilyUpdateRequest,
)
from src.modules.catalogue.application.dto.product_family_dto import CreateProductFamilyCommand
from src.modules.catalogue.application.dto.product_family_dto import UpdateProductFamilyCommand
from src.modules.catalogue.application.use_cases.product_family.archive_product_family import (
    ArchiveProductFamily,
)
from src.modules.catalogue.application.use_cases.product_family.create_product_family import (
    CreateProductFamily,
)
from src.modules.catalogue.application.use_cases.product_family.get_product_family import (
    GetProductFamilies,
)
from src.modules.catalogue.application.use_cases.product_family.get_product_family import (
    GetProductFamily,
)
from src.modules.catalogue.application.use_cases.product_family.move_product_family import (
    MoveProductFamily,
)
from src.modules.catalogue.application.use_cases.product_family.move_product_family import (
    PlaceProductFamily,
)
from src.modules.catalogue.application.use_cases.product_family.restore_product_family import (
    RestoreProductFamily,
)
from src.modules.catalogue.application.use_cases.product_family.update_product_family import (
    UpdateProductFamily,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.misc import get_tenant_zone
from src.modules.platform.adapters.inbound.api.schemas.list_move_schema import ListMoveRequest
from src.modules.platform.adapters.inbound.api.schemas.list_move_schema import ListPlaceRequest
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/", response_model=PageResponse[ProductFamilyResponse])
async def read_product_families(
    params: ProductFamilyFilterParams = Depends(),
    _: User = Depends(get_current_active_user),
    zone: tzinfo = Depends(get_tenant_zone),
    use_case: GetProductFamilies = Depends(get_product_families_use_case),
) -> PageResponse[ProductFamilyResponse]:
    result = await use_case.execute(params.to_dto(zone))
    return PageResponse.from_result(result, params, item_model=ProductFamilyResponse)


@router.post("/", response_model=ProductFamilyResponse, status_code=status.HTTP_201_CREATED)
async def create_product_family(
    body: ProductFamilyCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateProductFamily = Depends(get_create_product_family_use_case),
) -> ProductFamilyResponse:
    cmd = CreateProductFamilyCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, cmd=cmd)
    return ProductFamilyResponse.model_validate(result.model_dump())


@router.get("/{product_family_id}", response_model=ProductFamilyResponse)
async def read_product_family(
    product_family_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetProductFamily = Depends(get_product_family_use_case),
) -> ProductFamilyResponse:
    result = await use_case.execute(product_family_id=product_family_id)
    return ProductFamilyResponse.model_validate(result.model_dump())


@router.get("/{product_family_id}/changelog", response_model=list[str])
async def read_product_family_changelog(
    product_family_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetProductFamily = Depends(get_product_family_use_case),
) -> list[str]:
    return await use_case.changelog(product_family_id)


@router.put("/{product_family_id}", response_model=ProductFamilyResponse)
async def update_product_family(
    product_family_id: int,
    body: ProductFamilyUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateProductFamily = Depends(get_update_product_family_use_case),
) -> ProductFamilyResponse:
    cmd = UpdateProductFamilyCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, product_family_id=product_family_id, cmd=cmd)
    return ProductFamilyResponse.model_validate(result.model_dump())


@router.post("/{product_family_id}/archive", response_model=ProductFamilyResponse)
async def archive_product_family(
    product_family_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: ArchiveProductFamily = Depends(get_archive_product_family_use_case),
) -> ProductFamilyResponse:
    result = await use_case.execute(actor=actor, product_family_id=product_family_id)
    return ProductFamilyResponse.model_validate(result.model_dump())


@router.post("/{product_family_id}/restore", response_model=ProductFamilyResponse)
async def restore_product_family(
    product_family_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: RestoreProductFamily = Depends(get_restore_product_family_use_case),
) -> ProductFamilyResponse:
    result = await use_case.execute(actor=actor, product_family_id=product_family_id)
    return ProductFamilyResponse.model_validate(result.model_dump())


@router.post("/{product_family_id}/move", status_code=status.HTTP_204_NO_CONTENT)
async def move_product_family(
    product_family_id: int,
    body: ListMoveRequest,
    actor: User = Depends(get_current_active_user),
    use_case: MoveProductFamily = Depends(get_move_product_family_use_case),
) -> None:
    """Moves the entry one place up or down in the order pickers offer."""
    await use_case.execute(actor, product_family_id, body.direction)


@router.post("/{product_family_id}/place", status_code=status.HTTP_204_NO_CONTENT)
async def place_product_family(
    product_family_id: int,
    body: ListPlaceRequest,
    actor: User = Depends(get_current_active_user),
    use_case: PlaceProductFamily = Depends(get_place_product_family_use_case),
) -> None:
    """Puts the family next to another one, as dragging its row does."""
    await use_case.execute(
        actor, product_family_id, after_id=body.after_id, before_id=body.before_id
    )
