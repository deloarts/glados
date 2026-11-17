"""
The import profile a spreadsheet import reads before it parses a file. Any
signed-in user may read it; the import's own validate and commit routes
carry the import's permission.
"""

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.catalogue.adapters.inbound.api.deps.data_import import (
    get_data_import_profile_use_case,
)
from src.modules.catalogue.adapters.inbound.api.schemas.admin_settings_schema.data_import import (
    DataImportProfileResponse,
)
from src.modules.catalogue.application.dto.admin_settings_dto.data_import import (
    DataImportProfileResult,
)
from src.modules.catalogue.application.use_cases.data_import.get_data_import_profile import (
    GetDataImportProfile,
)
from src.modules.catalogue.domain.value_objects.data_import_type import DataImportType
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/profiles/{import_type}", response_model=DataImportProfileResponse)
async def get_data_import_profile(
    import_type: DataImportType,
    actor: User = Depends(get_current_active_user),
    use_case: GetDataImportProfile = Depends(get_data_import_profile_use_case),
) -> DataImportProfileResult:
    return await use_case.execute(actor=actor, import_type=import_type)
