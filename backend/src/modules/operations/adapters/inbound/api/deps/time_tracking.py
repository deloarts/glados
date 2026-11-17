"""
Use case factories: the time tracking admin settings (read, update,
connection test, key confirmation, purge of all stored credentials) and the
user's own time tracking credentials and month and year views.
"""

from fastapi import Depends

from src.modules.operations.adapters.inbound.api.deps.repositories import (
    get_operations_settings_repo,
)
from src.modules.operations.adapters.inbound.api.deps.repositories import (
    get_user_time_tracking_credentials_repo,
)
from src.modules.operations.adapters.inbound.api.deps.services import (
    get_time_tracking_provider_factory,
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
from src.modules.operations.application.use_cases.time_tracking.check_my_time_tracking_access import (
    CheckMyTimeTrackingAccess,
)
from src.modules.operations.application.use_cases.time_tracking.delete_my_time_tracking_credentials import (
    DeleteMyTimeTrackingCredentials,
)
from src.modules.operations.application.use_cases.time_tracking.get_my_time_tracking_credentials import (
    GetMyTimeTrackingCredentials,
)
from src.modules.operations.application.use_cases.time_tracking.get_my_time_tracking_month import (
    GetMyTimeTrackingMonth,
)
from src.modules.operations.application.use_cases.time_tracking.get_my_time_tracking_year import (
    GetMyTimeTrackingYear,
)
from src.modules.operations.application.use_cases.time_tracking.save_my_time_tracking_credentials import (
    SaveMyTimeTrackingCredentials,
)
from src.modules.operations.ports.outbound.operations_settings_repository import (
    IOperationsSettingsRepository,
)
from src.modules.operations.ports.outbound.repositories.user_time_tracking_credentials_repository import (
    IUserTimeTrackingCredentialsRepository,
)
from src.modules.operations.ports.outbound.time_tracking_provider_port import (
    ITimeTrackingProviderFactory,
)
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.adapters.inbound.api.deps.repositories import get_user_repo
from src.modules.platform.adapters.inbound.api.deps.services import get_login_attempt_tracker
from src.modules.platform.ports.outbound.login_attempt_tracker_port import ILoginAttemptTracker
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork

# ── Admin: time tracking settings ─────────────────────────────────────


def get_time_tracking_settings_use_case(
    repo: IOperationsSettingsRepository = Depends(get_operations_settings_repo),
    credentials_repo: IUserTimeTrackingCredentialsRepository = Depends(
        get_user_time_tracking_credentials_repo
    ),
    user_repo: IUserRepository = Depends(get_user_repo),
) -> GetTimeTrackingSettings:
    return GetTimeTrackingSettings(repo, credentials_repo, user_repo)


def get_update_time_tracking_settings_use_case(
    repo: IOperationsSettingsRepository = Depends(get_operations_settings_repo),
    credentials_repo: IUserTimeTrackingCredentialsRepository = Depends(
        get_user_time_tracking_credentials_repo
    ),
    user_repo: IUserRepository = Depends(get_user_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateTimeTrackingSettings:
    return UpdateTimeTrackingSettings(repo, credentials_repo, user_repo, uow=uow)


def get_verify_time_tracking_service_use_case(
    provider_factory: ITimeTrackingProviderFactory = Depends(get_time_tracking_provider_factory),
    repo: IOperationsSettingsRepository = Depends(get_operations_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> VerifyTimeTrackingService:
    return VerifyTimeTrackingService(provider_factory=provider_factory, repo=repo, uow=uow)


def get_confirm_time_tracking_key_use_case(
    provider_factory: ITimeTrackingProviderFactory = Depends(get_time_tracking_provider_factory),
    repo: IOperationsSettingsRepository = Depends(get_operations_settings_repo),
    credentials_repo: IUserTimeTrackingCredentialsRepository = Depends(
        get_user_time_tracking_credentials_repo
    ),
    user_repo: IUserRepository = Depends(get_user_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> ConfirmTimeTrackingKey:
    return ConfirmTimeTrackingKey(provider_factory, repo, credentials_repo, user_repo, uow=uow)


def get_purge_time_tracking_credentials_use_case(
    repo: IOperationsSettingsRepository = Depends(get_operations_settings_repo),
    credentials_repo: IUserTimeTrackingCredentialsRepository = Depends(
        get_user_time_tracking_credentials_repo
    ),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> PurgeTimeTrackingCredentials:
    return PurgeTimeTrackingCredentials(repo, credentials_repo, uow=uow)


# ── The user's own time tracking ──────────────────────────────────────


def get_my_time_tracking_credentials_use_case(
    settings_repo: IOperationsSettingsRepository = Depends(get_operations_settings_repo),
    credentials_repo: IUserTimeTrackingCredentialsRepository = Depends(
        get_user_time_tracking_credentials_repo
    ),
) -> GetMyTimeTrackingCredentials:
    return GetMyTimeTrackingCredentials(settings_repo, credentials_repo)


def get_save_my_time_tracking_credentials_use_case(
    settings_repo: IOperationsSettingsRepository = Depends(get_operations_settings_repo),
    credentials_repo: IUserTimeTrackingCredentialsRepository = Depends(
        get_user_time_tracking_credentials_repo
    ),
    provider_factory: ITimeTrackingProviderFactory = Depends(get_time_tracking_provider_factory),
    rate_tracker: ILoginAttemptTracker = Depends(get_login_attempt_tracker),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> SaveMyTimeTrackingCredentials:
    return SaveMyTimeTrackingCredentials(
        settings_repo, credentials_repo, provider_factory, rate_tracker, uow=uow
    )


def get_check_my_time_tracking_access_use_case(
    settings_repo: IOperationsSettingsRepository = Depends(get_operations_settings_repo),
    credentials_repo: IUserTimeTrackingCredentialsRepository = Depends(
        get_user_time_tracking_credentials_repo
    ),
    provider_factory: ITimeTrackingProviderFactory = Depends(get_time_tracking_provider_factory),
    rate_tracker: ILoginAttemptTracker = Depends(get_login_attempt_tracker),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> CheckMyTimeTrackingAccess:
    return CheckMyTimeTrackingAccess(
        settings_repo, credentials_repo, provider_factory, rate_tracker, uow=uow
    )


def get_delete_my_time_tracking_credentials_use_case(
    credentials_repo: IUserTimeTrackingCredentialsRepository = Depends(
        get_user_time_tracking_credentials_repo
    ),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> DeleteMyTimeTrackingCredentials:
    return DeleteMyTimeTrackingCredentials(credentials_repo, uow=uow)


def get_my_time_tracking_month_use_case(
    settings_repo: IOperationsSettingsRepository = Depends(get_operations_settings_repo),
    credentials_repo: IUserTimeTrackingCredentialsRepository = Depends(
        get_user_time_tracking_credentials_repo
    ),
    provider_factory: ITimeTrackingProviderFactory = Depends(get_time_tracking_provider_factory),
    rate_tracker: ILoginAttemptTracker = Depends(get_login_attempt_tracker),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> GetMyTimeTrackingMonth:
    return GetMyTimeTrackingMonth(
        settings_repo, credentials_repo, provider_factory, rate_tracker, uow=uow
    )


def get_my_time_tracking_year_use_case(
    settings_repo: IOperationsSettingsRepository = Depends(get_operations_settings_repo),
    credentials_repo: IUserTimeTrackingCredentialsRepository = Depends(
        get_user_time_tracking_credentials_repo
    ),
    provider_factory: ITimeTrackingProviderFactory = Depends(get_time_tracking_provider_factory),
    rate_tracker: ILoginAttemptTracker = Depends(get_login_attempt_tracker),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> GetMyTimeTrackingYear:
    return GetMyTimeTrackingYear(
        settings_repo, credentials_repo, provider_factory, rate_tracker, uow=uow
    )
