"""
Admin settings endpoints for the time tracking tab: the time tracking
service, its connection test, the confirmation of its credential key, and
the purge of every user's stored time tracking credentials. Reads require
read:settings, everything else write:settings. The routes never echo
request input in a validation error, since requests may carry the API key.
"""

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.operations.adapters.inbound.api.deps.time_tracking import (
    get_confirm_time_tracking_key_use_case,
)
from src.modules.operations.adapters.inbound.api.deps.time_tracking import (
    get_purge_time_tracking_credentials_use_case,
)
from src.modules.operations.adapters.inbound.api.deps.time_tracking import (
    get_time_tracking_settings_use_case,
)
from src.modules.operations.adapters.inbound.api.deps.time_tracking import (
    get_update_time_tracking_settings_use_case,
)
from src.modules.operations.adapters.inbound.api.deps.time_tracking import (
    get_verify_time_tracking_service_use_case,
)
from src.modules.operations.adapters.inbound.api.schemas.admin_settings_schema.time_tracking import (
    AdminTimeTrackingSettingsResponse,
)
from src.modules.operations.adapters.inbound.api.schemas.admin_settings_schema.time_tracking import (
    ConfirmTimeTrackingKeyRequest,
)
from src.modules.operations.adapters.inbound.api.schemas.admin_settings_schema.time_tracking import (
    PurgeTimeTrackingCredentialsResponse,
)
from src.modules.operations.adapters.inbound.api.schemas.admin_settings_schema.time_tracking import (
    TimeTrackingServiceTestResponse,
)
from src.modules.operations.adapters.inbound.api.schemas.admin_settings_schema.time_tracking import (
    UpdateTimeTrackingSettingsRequest,
)
from src.modules.operations.adapters.inbound.api.schemas.admin_settings_schema.time_tracking import (
    VerifyTimeTrackingServiceRequest,
)
from src.modules.operations.application.dto.admin_settings_dto.time_tracking import (
    AdminTimeTrackingSettingsResult,
)
from src.modules.operations.application.dto.admin_settings_dto.time_tracking import (
    ConfirmTimeTrackingKeyCommand,
)
from src.modules.operations.application.dto.admin_settings_dto.time_tracking import (
    PurgeTimeTrackingCredentialsResult,
)
from src.modules.operations.application.dto.admin_settings_dto.time_tracking import (
    TimeTrackingServiceTestResult,
)
from src.modules.operations.application.dto.admin_settings_dto.time_tracking import (
    UpdateTimeTrackingSettingsCommand,
)
from src.modules.operations.application.dto.admin_settings_dto.time_tracking import (
    VerifyTimeTrackingServiceCommand,
)
from src.modules.operations.application.use_cases.admin_settings.confirm_time_tracking_key import (
    ConfirmTimeTrackingKey,
)
from src.modules.operations.application.use_cases.admin_settings.get_time_tracking_settings import (
    GetTimeTrackingSettings,
)
from src.modules.operations.application.use_cases.admin_settings.purge_time_tracking_credentials import (
    PurgeTimeTrackingCredentials,
)
from src.modules.operations.application.use_cases.admin_settings.update_time_tracking_settings import (
    UpdateTimeTrackingSettings,
)
from src.modules.operations.application.use_cases.admin_settings.verify_time_tracking_service import (
    VerifyTimeTrackingService,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.no_echo_route import NoInputEchoRoute
from src.modules.platform.domain.entities.user import User

router = APIRouter(route_class=NoInputEchoRoute)


@router.get("/time-tracking", response_model=AdminTimeTrackingSettingsResponse)
async def get_time_tracking_settings(
    actor: User = Depends(get_current_active_user),
    use_case: GetTimeTrackingSettings = Depends(get_time_tracking_settings_use_case),
) -> AdminTimeTrackingSettingsResult:
    return await use_case.execute(actor=actor)


@router.put("/time-tracking", response_model=AdminTimeTrackingSettingsResponse)
async def update_time_tracking_settings(
    body: UpdateTimeTrackingSettingsRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateTimeTrackingSettings = Depends(get_update_time_tracking_settings_use_case),
) -> AdminTimeTrackingSettingsResult:
    """Configure the time tracking service. Enabling needs a service URL and
    an API key. A changed service URL clears the confirmed credential key,
    so time tracking is unavailable until the new service's key is
    confirmed."""
    cmd = UpdateTimeTrackingSettingsCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)


@router.post("/time-tracking/test", response_model=TimeTrackingServiceTestResponse)
async def test_time_tracking_service(
    body: VerifyTimeTrackingServiceRequest,
    actor: User = Depends(get_current_active_user),
    use_case: VerifyTimeTrackingService = Depends(get_verify_time_tracking_service_use_case),
) -> TimeTrackingServiceTestResult:
    """Test the given or stored time tracking service: its version, contract
    and credential key, and the version and default project of the system
    behind it. Needs no user credentials and stores nothing."""
    cmd = VerifyTimeTrackingServiceCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)


@router.post("/time-tracking/confirm-key", response_model=AdminTimeTrackingSettingsResponse)
async def confirm_time_tracking_key(
    body: ConfirmTimeTrackingKeyRequest,
    actor: User = Depends(get_current_active_user),
    use_case: ConfirmTimeTrackingKey = Depends(get_confirm_time_tracking_key_use_case),
) -> AdminTimeTrackingSettingsResult:
    """Confirm the credential key the saved service serves, by the key id
    the connection test showed. Credentials sealed for another key stop
    working until their users save them again."""
    cmd = ConfirmTimeTrackingKeyCommand(credential_key_id=body.credential_key_id)
    return await use_case.execute(actor=actor, cmd=cmd)


@router.delete("/time-tracking/credentials", response_model=PurgeTimeTrackingCredentialsResponse)
async def purge_time_tracking_credentials(
    actor: User = Depends(get_current_active_user),
    use_case: PurgeTimeTrackingCredentials = Depends(get_purge_time_tracking_credentials_use_case),
) -> PurgeTimeTrackingCredentialsResult:
    """Delete every user's stored time tracking credentials."""
    return await use_case.execute(actor=actor)
