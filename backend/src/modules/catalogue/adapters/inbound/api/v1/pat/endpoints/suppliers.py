"""
PAT surface, read-only supplier access.
"""

from datetime import tzinfo

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.catalogue.adapters.inbound.api.deps.catalogue import get_supplier_use_case
from src.modules.catalogue.adapters.inbound.api.deps.catalogue import get_suppliers_use_case
from src.modules.catalogue.adapters.inbound.api.schemas.supplier_schema import SupplierFilterParams
from src.modules.catalogue.adapters.inbound.api.schemas.supplier_schema import SupplierResponse
from src.modules.catalogue.application.use_cases.supplier.get_supplier import GetSupplier
from src.modules.catalogue.application.use_cases.supplier.get_supplier import GetSuppliers
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_user_pat
from src.modules.platform.adapters.inbound.api.deps.misc import get_tenant_zone
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/", response_model=PageResponse[SupplierResponse])
async def read_suppliers(
    params: SupplierFilterParams = Depends(),
    _: User = Depends(get_current_user_pat),
    zone: tzinfo = Depends(get_tenant_zone),
    use_case: GetSuppliers = Depends(get_suppliers_use_case),
) -> PageResponse[SupplierResponse]:
    result = await use_case.execute(params.to_dto(zone))
    return PageResponse.from_result(result, params, item_model=SupplierResponse)


@router.get("/{supplier_id}", response_model=SupplierResponse)
async def read_supplier(
    supplier_id: int,
    _: User = Depends(get_current_user_pat),
    use_case: GetSupplier = Depends(get_supplier_use_case),
) -> SupplierResponse:
    result = await use_case.execute(supplier_id=supplier_id)
    return SupplierResponse.model_validate(result.model_dump())
