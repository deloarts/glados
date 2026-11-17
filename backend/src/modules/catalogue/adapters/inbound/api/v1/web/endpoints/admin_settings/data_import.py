"""
Admin settings endpoints for the Data import tab: the import profile of
every spreadsheet import. Reads require read:settings, writes
write:settings.
"""

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.catalogue.adapters.inbound.api.deps.data_import import (
    get_data_import_settings_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.data_import import (
    get_update_data_import_settings_use_case,
)
from src.modules.catalogue.adapters.inbound.api.schemas.admin_settings_schema.data_import import (
    AdminDataImportSettingsResponse,
)
from src.modules.catalogue.adapters.inbound.api.schemas.admin_settings_schema.data_import import (
    UpdateDataImportSettingsRequest,
)
from src.modules.catalogue.application.dto.admin_settings_dto.data_import import (
    AdminDataImportSettingsResult,
)
from src.modules.catalogue.application.dto.admin_settings_dto.data_import import (
    UpdateDataImportSettingsCommand,
)
from src.modules.catalogue.application.use_cases.admin_settings.get_data_import_settings import (
    GetDataImportSettings,
)
from src.modules.catalogue.application.use_cases.admin_settings.update_data_import_settings import (
    UpdateDataImportSettings,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/data-import", response_model=AdminDataImportSettingsResponse)
async def get_data_import_settings(
    actor: User = Depends(get_current_active_user),
    use_case: GetDataImportSettings = Depends(get_data_import_settings_use_case),
) -> AdminDataImportSettingsResult:
    return await use_case.execute(actor=actor)


@router.put("/data-import", response_model=AdminDataImportSettingsResponse)
async def update_data_import_settings(
    body: UpdateDataImportSettingsRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateDataImportSettings = Depends(get_update_data_import_settings_use_case),
) -> AdminDataImportSettingsResult:
    """Replace the listed import profiles; unlisted import types keep theirs.
    A column name may map to one field of a profile only."""
    cmd = UpdateDataImportSettingsCommand(**body.model_dump(mode="json"))
    return await use_case.execute(actor=actor, cmd=cmd)
