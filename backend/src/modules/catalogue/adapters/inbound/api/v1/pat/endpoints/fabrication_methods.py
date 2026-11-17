"""
PAT surface, read-only fabrication method access.
"""

from datetime import tzinfo

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.catalogue.adapters.inbound.api.deps.items import get_fabrication_method_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_fabrication_methods_use_case
from src.modules.catalogue.adapters.inbound.api.schemas.fabrication_method_schema import (
    FabricationMethodFilterParams,
)
from src.modules.catalogue.adapters.inbound.api.schemas.fabrication_method_schema import (
    FabricationMethodResponse,
)
from src.modules.catalogue.application.use_cases.fabrication_method.get_fabrication_method import (
    GetFabricationMethod,
)
from src.modules.catalogue.application.use_cases.fabrication_method.get_fabrication_method import (
    GetFabricationMethods,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_user_pat
from src.modules.platform.adapters.inbound.api.deps.misc import get_tenant_zone
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.label_languages import label_languages

router = APIRouter()


@router.get("/", response_model=PageResponse[FabricationMethodResponse])
async def read_fabrication_methods(
    params: FabricationMethodFilterParams = Depends(),
    _: User = Depends(get_current_user_pat),
    zone: tzinfo = Depends(get_tenant_zone),
    use_case: GetFabricationMethods = Depends(get_fabrication_methods_use_case),
) -> PageResponse[FabricationMethodResponse]:
    result = await use_case.execute(params.to_dto(zone, label_languages()))
    return PageResponse.from_result(result, params, item_model=FabricationMethodResponse)


@router.get("/{fabrication_method_id}", response_model=FabricationMethodResponse)
async def read_fabrication_method(
    fabrication_method_id: int,
    _: User = Depends(get_current_user_pat),
    use_case: GetFabricationMethod = Depends(get_fabrication_method_use_case),
) -> FabricationMethodResponse:
    result = await use_case.execute(fabrication_method_id=fabrication_method_id)
    return FabricationMethodResponse.model_validate(result.model_dump())
