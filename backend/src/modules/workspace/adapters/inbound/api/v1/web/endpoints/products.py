"""
Web surface product endpoints.
"""

from datetime import date

from fastapi import Depends
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.user import User
from src.modules.workspace.adapters.inbound.api.deps.products import get_archive_product_use_case
from src.modules.workspace.adapters.inbound.api.deps.products import get_create_product_use_case
from src.modules.workspace.adapters.inbound.api.deps.products import get_my_products_use_case
from src.modules.workspace.adapters.inbound.api.deps.products import get_product_by_number_use_case
from src.modules.workspace.adapters.inbound.api.deps.products import get_product_summary_use_case
from src.modules.workspace.adapters.inbound.api.deps.products import get_product_use_case
from src.modules.workspace.adapters.inbound.api.deps.products import get_products_use_case
from src.modules.workspace.adapters.inbound.api.deps.products import get_restore_product_use_case
from src.modules.workspace.adapters.inbound.api.deps.products import get_update_product_use_case
from src.modules.workspace.adapters.inbound.api.schemas.product_schema import LegalBasis
from src.modules.workspace.adapters.inbound.api.schemas.product_schema import ProductCreateRequest
from src.modules.workspace.adapters.inbound.api.schemas.product_schema import ProductFilterParams
from src.modules.workspace.adapters.inbound.api.schemas.product_schema import ProductResponse
from src.modules.workspace.adapters.inbound.api.schemas.product_schema import ProductUpdateRequest
from src.modules.workspace.adapters.inbound.api.schemas.project_schema import ProjectSummaryResponse
from src.modules.workspace.application.dto.product_dto import CreateProductCommand
from src.modules.workspace.application.dto.product_dto import UpdateProductCommand
from src.modules.workspace.application.use_cases.product.archive_product import ArchiveProduct
from src.modules.workspace.application.use_cases.product.create_product import CreateProduct
from src.modules.workspace.application.use_cases.product.get_product import GetMyProducts
from src.modules.workspace.application.use_cases.product.get_product import GetProduct
from src.modules.workspace.application.use_cases.product.get_product import GetProductByNumber
from src.modules.workspace.application.use_cases.product.get_product import GetProducts
from src.modules.workspace.application.use_cases.product.get_product_summary import (
    GetProductSummary,
)
from src.modules.workspace.application.use_cases.product.restore_product import RestoreProduct
from src.modules.workspace.application.use_cases.product.update_product import UpdateProduct
from src.modules.workspace.ports.outbound.project_work_port import ProjectSummaryRow

router = APIRouter()


class ProductWebResponse(ProductResponse):
    """Web-only extension of ProductResponse: the machine data for the CE
    assessment is shown and edited on the product page and copied into its
    checklists. The SolidWorks add-in never reads it, so it is kept off the
    shared response class the PAT surface also returns, to avoid widening
    that frozen contract."""

    designation: str | None
    machine_type: str | None
    installation_site: str | None
    installation_location: str | None
    planned_placing_on_market: date | None
    legal_basis: LegalBasis | None
    plc_environment_id: int | None
    contains_pneumatics: bool
    contains_hydraulics: bool
    contains_electrics: bool
    contains_robotics: bool


# ── GET /products/ ────────────────────────────────────────────────────


@router.get("/", response_model=PageResponse[ProductWebResponse])
async def read_products(
    params: ProductFilterParams = Depends(),
    _: User = Depends(get_current_active_user),
    use_case: GetProducts = Depends(get_products_use_case),
) -> PageResponse[ProductWebResponse]:
    result = await use_case.execute(params.to_dto())
    return PageResponse.from_result(result, params, item_model=ProductWebResponse)


# ── POST /products/ ───────────────────────────────────────────────────


@router.post("/", response_model=ProductWebResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    body: ProductCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateProduct = Depends(get_create_product_use_case),
) -> ProductWebResponse:
    cmd = CreateProductCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, cmd=cmd)
    return ProductWebResponse.model_validate(result.model_dump())


# ── GET /products/my ──────────────────────────────────────────────────


@router.get("/my", response_model=list[ProductWebResponse])
async def read_my_products(
    current_user: User = Depends(get_current_active_user),
    use_case: GetMyProducts = Depends(get_my_products_use_case),
) -> list[ProductWebResponse]:
    results = await use_case.execute(user_id=current_user.id)
    return [ProductWebResponse.model_validate(r.model_dump()) for r in results]


# ── GET /products/{product_id}/summary ───────────────────────────────


@router.get("/{product_id}/summary", response_model=ProjectSummaryResponse)
async def get_product_summary(
    product_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetProductSummary = Depends(get_product_summary_use_case),
) -> ProjectSummaryRow:
    """The project summary rolled up over all projects built on the product."""
    return await use_case.execute(product_id)


# ── GET /products/{product_id} ────────────────────────────────────────


@router.get("/{product_id}", response_model=ProductWebResponse)
async def read_product_by_id(
    product_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetProduct = Depends(get_product_use_case),
) -> ProductWebResponse:
    result = await use_case.execute(product_id=product_id)
    return ProductWebResponse.model_validate(result.model_dump())


# ── GET /products/number/{product_number} ────────────────────────────


@router.get("/number/{product_number}", response_model=ProductWebResponse)
async def read_product_by_number(
    product_number: str,
    _: User = Depends(get_current_active_user),
    use_case: GetProductByNumber = Depends(get_product_by_number_use_case),
) -> ProductWebResponse:
    result = await use_case.execute(product_number=product_number)
    return ProductWebResponse.model_validate(result.model_dump())


# ── PUT /products/{product_id} ────────────────────────────────────────


@router.put("/{product_id}", response_model=ProductWebResponse)
async def update_product(
    product_id: int,
    body: ProductUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateProduct = Depends(get_update_product_use_case),
) -> ProductWebResponse:
    cmd = UpdateProductCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, product_id=product_id, cmd=cmd)
    return ProductWebResponse.model_validate(result.model_dump())


# ── POST /products/{product_id}/archive ───────────────────────────────


@router.post("/{product_id}/archive", response_model=ProductWebResponse)
async def archive_product(
    product_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: ArchiveProduct = Depends(get_archive_product_use_case),
) -> ProductWebResponse:
    result = await use_case.execute(actor=actor, product_id=product_id)
    return ProductWebResponse.model_validate(result.model_dump())


# ── POST /products/{product_id}/restore ───────────────────────────────


@router.post("/{product_id}/restore", response_model=ProductWebResponse)
async def restore_product(
    product_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: RestoreProduct = Depends(get_restore_product_use_case),
) -> ProductWebResponse:
    result = await use_case.execute(actor=actor, product_id=product_id)
    return ProductWebResponse.model_validate(result.model_dump())
