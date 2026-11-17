"""
PAT surface, read-only inspection method access.
"""

from datetime import tzinfo

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.catalogue.adapters.inbound.api.deps.items import get_inspection_method_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_inspection_methods_use_case
from src.modules.catalogue.adapters.inbound.api.schemas.inspection_method_schema import (
    InspectionMethodFilterParams,
)
from src.modules.catalogue.adapters.inbound.api.schemas.inspection_method_schema import (
    InspectionMethodResponse,
)
from src.modules.catalogue.application.use_cases.inspection_method.get_inspection_method import (
    GetInspectionMethod,
)
from src.modules.catalogue.application.use_cases.inspection_method.get_inspection_method import (
    GetInspectionMethods,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_user_pat
from src.modules.platform.adapters.inbound.api.deps.misc import get_tenant_zone
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.label_languages import label_languages

router = APIRouter()


@router.get("/", response_model=PageResponse[InspectionMethodResponse])
async def read_inspection_methods(
    params: InspectionMethodFilterParams = Depends(),
    _: User = Depends(get_current_user_pat),
    zone: tzinfo = Depends(get_tenant_zone),
    use_case: GetInspectionMethods = Depends(get_inspection_methods_use_case),
) -> PageResponse[InspectionMethodResponse]:
    result = await use_case.execute(params.to_dto(zone, label_languages()))
    return PageResponse.from_result(result, params, item_model=InspectionMethodResponse)


@router.get("/{inspection_method_id}", response_model=InspectionMethodResponse)
async def read_inspection_method(
    inspection_method_id: int,
    _: User = Depends(get_current_user_pat),
    use_case: GetInspectionMethod = Depends(get_inspection_method_use_case),
) -> InspectionMethodResponse:
    result = await use_case.execute(inspection_method_id=inspection_method_id)
    return InspectionMethodResponse.model_validate(result.model_dump())
