"""
PAT surface, read-only settings the SolidWorks add-in needs at the
workstation. Currently just the field mapping (docs/reference/field-ownership.md
sections 2, 3 and 6). Standard PAT auth, no extra permission: non-sensitive
configuration, same posture as the other PAT GET endpoints.
"""

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.external_data.adapters.inbound.api.deps.settings import get_field_mapping_use_case
from src.modules.external_data.adapters.inbound.api.schemas.field_mapping_schema import (
    FieldMappingResponse,
)
from src.modules.external_data.application.use_cases.admin_settings.get_field_mapping import (
    GetFieldMapping,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_user_pat
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/field-mapping", response_model=FieldMappingResponse)
async def read_field_mapping(
    _: User = Depends(get_current_user_pat),
    use_case: GetFieldMapping = Depends(get_field_mapping_use_case),
) -> FieldMappingResponse:
    result = await use_case.execute()
    return FieldMappingResponse.model_validate(result.model_dump())
