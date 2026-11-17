"""Use case factories: user accounts, API keys, personal access tokens."""

from fastapi import Depends

from src.modules.platform.adapters.inbound.api.deps.bindings import get_user_held_credentials
from src.modules.platform.adapters.inbound.api.deps.database import get_transactional_event_bus
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.adapters.inbound.api.deps.repositories import get_api_key_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_api_key_usage_log_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_pat_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_pat_usage_log_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_platform_settings_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_trusted_device_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_user_group_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_user_pdm_link_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_user_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_user_session_repo
from src.modules.platform.adapters.inbound.api.deps.services import get_login_attempt_tracker
from src.modules.platform.adapters.inbound.api.deps.services import get_mail_service
from src.modules.platform.adapters.inbound.api.deps.services import get_optional_ldap_authenticator
from src.modules.platform.adapters.inbound.api.deps.services import get_optional_storage_adapter
from src.modules.platform.adapters.inbound.api.deps.services import get_security_audit
from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.application.use_cases.api_key.create_api_key import CreateApiKey
from src.modules.platform.application.use_cases.api_key.get_api_key import GetApiKey
from src.modules.platform.application.use_cases.api_key.get_api_key import GetApiKeys
from src.modules.platform.application.use_cases.api_key.get_api_key_usage_log import (
    GetApiKeyUsageLog,
)
from src.modules.platform.application.use_cases.api_key.revoke_all_api_keys import RevokeAllApiKeys
from src.modules.platform.application.use_cases.api_key.revoke_api_key import RevokeApiKey
from src.modules.platform.application.use_cases.pat.create_pat import CreatePat
from src.modules.platform.application.use_cases.pat.create_pat import CreatePatWithPassword
from src.modules.platform.application.use_cases.pat.get_pat import GetPat
from src.modules.platform.application.use_cases.pat.get_pat import GetPats
from src.modules.platform.application.use_cases.pat.get_pat_usage_log import GetPatUsageLog
from src.modules.platform.application.use_cases.pat.revoke_all_pats import RevokeAllPats
from src.modules.platform.application.use_cases.pat.revoke_pat import RevokePat
from src.modules.platform.application.use_cases.user.create_user import CreateUser
from src.modules.platform.application.use_cases.user.delete_user import DeleteUser
from src.modules.platform.application.use_cases.user.delete_user_avatar import DeleteUserAvatar
from src.modules.platform.application.use_cases.user.force_logout_all_users import (
    ForceLogoutAllUsers,
)
from src.modules.platform.application.use_cases.user.force_logout_user import ForceLogoutUser
from src.modules.platform.application.use_cases.user.get_user import GetUser
from src.modules.platform.application.use_cases.user.get_user import GetUserDirectory
from src.modules.platform.application.use_cases.user.get_user import GetUsers
from src.modules.platform.application.use_cases.user.get_user_avatar import GetUserAvatar
from src.modules.platform.application.use_cases.user.password_confirmation import (
    PasswordConfirmation,
)
from src.modules.platform.application.use_cases.user.reset_user_totp import ResetUserTotp
from src.modules.platform.application.use_cases.user.update_user import UpdateUser
from src.modules.platform.application.use_cases.user.upload_user_avatar import UploadUserAvatar
from src.modules.platform.application.use_cases.user_group.user_groups import CreateUserGroup
from src.modules.platform.application.use_cases.user_group.user_groups import DeleteUserGroup
from src.modules.platform.application.use_cases.user_group.user_groups import ListUserGroups
from src.modules.platform.application.use_cases.user_group.user_groups import UpdateUserGroup
from src.modules.platform.infrastructure.config.settings import cfg
from src.modules.platform.infrastructure.security.hashing import aget_hash
from src.modules.platform.infrastructure.security.hashing import averify_hash
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.ldap_authenticator_port import ILdapAuthenticator
from src.modules.platform.ports.outbound.login_attempt_tracker_port import ILoginAttemptTracker
from src.modules.platform.ports.outbound.mail_service_port import IMailService
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.repositories.api_key_repository import IApiKeyRepository
from src.modules.platform.ports.outbound.repositories.api_key_usage_log_repository import (
    IApiKeyUsageLogRepository,
)
from src.modules.platform.ports.outbound.repositories.pat_repository import IPatRepository
from src.modules.platform.ports.outbound.repositories.pat_usage_log_repository import (
    IPatUsageLogRepository,
)
from src.modules.platform.ports.outbound.repositories.trusted_device_repository import (
    ITrustedDeviceRepository,
)
from src.modules.platform.ports.outbound.repositories.user_group_repository import (
    IUserGroupRepository,
)
from src.modules.platform.ports.outbound.repositories.user_pdm_link_repository import (
    IUserPdmLinkRepository,
)
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.repositories.user_session_repository import (
    IUserSessionRepository,
)
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.platform.ports.outbound.user_held_credentials_port import IUserHeldCredentials


def get_create_user_use_case(
    user_repo: IUserRepository = Depends(get_user_repo),
    mail_service: IMailService = Depends(get_mail_service),
    settings_repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    group_repo: IUserGroupRepository = Depends(get_user_group_repo),
    audit: SecurityAudit = Depends(get_security_audit),
) -> CreateUser:
    return CreateUser(
        user_repo=user_repo,
        mail_service=mail_service,
        hash_fn=aget_hash,
        settings_repo=settings_repo,
        uow=uow,
        group_repo=group_repo,
        audit=audit,
    )


def get_password_confirmation(
    user_repo: IUserRepository = Depends(get_user_repo),
    settings_repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    attempts: ILoginAttemptTracker = Depends(get_login_attempt_tracker),
    ldap: ILdapAuthenticator | None = Depends(get_optional_ldap_authenticator),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    audit: SecurityAudit = Depends(get_security_audit),
) -> PasswordConfirmation:
    return PasswordConfirmation(
        user_repo=user_repo,
        settings_repo=settings_repo,
        attempts=attempts,
        ldap=ldap,
        uow=uow,
        verify_fn=averify_hash,
        audit=audit,
    )


def get_update_user_use_case(
    user_repo: IUserRepository = Depends(get_user_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    session_repo: IUserSessionRepository = Depends(get_user_session_repo),
    trusted_device_repo: ITrustedDeviceRepository = Depends(get_trusted_device_repo),
    link_repo: IUserPdmLinkRepository = Depends(get_user_pdm_link_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    time_tracking_credentials_repo: IUserHeldCredentials = Depends(get_user_held_credentials),
    group_repo: IUserGroupRepository = Depends(get_user_group_repo),
    pat_repo: IPatRepository = Depends(get_pat_repo),
    password_confirmation: PasswordConfirmation = Depends(get_password_confirmation),
    audit: SecurityAudit = Depends(get_security_audit),
) -> UpdateUser:
    return UpdateUser(
        user_repo=user_repo,
        min_password_length=cfg.security.min_pw_len,
        hash_fn=aget_hash,
        session_repo=session_repo,
        trusted_device_repo=trusted_device_repo,
        link_repo=link_repo,
        event_bus=event_bus,
        uow=uow,
        time_tracking_credentials_repo=time_tracking_credentials_repo,
        group_repo=group_repo,
        pat_repo=pat_repo,
        password_confirmation=password_confirmation,
        audit=audit,
    )


def get_user_use_case(
    user_repo: IUserRepository = Depends(get_user_repo),
    link_repo: IUserPdmLinkRepository = Depends(get_user_pdm_link_repo),
) -> GetUser:
    return GetUser(user_repo=user_repo, link_repo=link_repo)


def get_users_use_case(
    user_repo: IUserRepository = Depends(get_user_repo),
    link_repo: IUserPdmLinkRepository = Depends(get_user_pdm_link_repo),
) -> GetUsers:
    return GetUsers(user_repo=user_repo, link_repo=link_repo)


def get_user_directory_use_case(
    user_repo: IUserRepository = Depends(get_user_repo),
) -> GetUserDirectory:
    return GetUserDirectory(user_repo=user_repo)


def get_delete_user_use_case(
    user_repo: IUserRepository = Depends(get_user_repo),
    link_repo: IUserPdmLinkRepository = Depends(get_user_pdm_link_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    time_tracking_credentials_repo: IUserHeldCredentials = Depends(get_user_held_credentials),
    audit: SecurityAudit = Depends(get_security_audit),
) -> DeleteUser:
    return DeleteUser(
        user_repo=user_repo,
        link_repo=link_repo,
        uow=uow,
        time_tracking_credentials_repo=time_tracking_credentials_repo,
        audit=audit,
    )


def get_reset_user_totp_use_case(
    user_repo: IUserRepository = Depends(get_user_repo),
    trusted_device_repo: ITrustedDeviceRepository = Depends(get_trusted_device_repo),
    link_repo: IUserPdmLinkRepository = Depends(get_user_pdm_link_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    audit: SecurityAudit = Depends(get_security_audit),
) -> ResetUserTotp:
    return ResetUserTotp(
        user_repo=user_repo,
        trusted_device_repo=trusted_device_repo,
        link_repo=link_repo,
        uow=uow,
        audit=audit,
    )


def get_force_logout_user_use_case(
    user_repo: IUserRepository = Depends(get_user_repo),
    pat_repo: IPatRepository = Depends(get_pat_repo),
    session_repo: IUserSessionRepository = Depends(get_user_session_repo),
    trusted_device_repo: ITrustedDeviceRepository = Depends(get_trusted_device_repo),
    link_repo: IUserPdmLinkRepository = Depends(get_user_pdm_link_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    audit: SecurityAudit = Depends(get_security_audit),
) -> ForceLogoutUser:
    return ForceLogoutUser(
        user_repo=user_repo,
        pat_repo=pat_repo,
        session_repo=session_repo,
        trusted_device_repo=trusted_device_repo,
        link_repo=link_repo,
        event_bus=event_bus,
        uow=uow,
        audit=audit,
    )


def get_force_logout_all_users_use_case(
    user_repo: IUserRepository = Depends(get_user_repo),
    pat_repo: IPatRepository = Depends(get_pat_repo),
    session_repo: IUserSessionRepository = Depends(get_user_session_repo),
    trusted_device_repo: ITrustedDeviceRepository = Depends(get_trusted_device_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    audit: SecurityAudit = Depends(get_security_audit),
) -> ForceLogoutAllUsers:
    return ForceLogoutAllUsers(
        user_repo=user_repo,
        pat_repo=pat_repo,
        session_repo=session_repo,
        trusted_device_repo=trusted_device_repo,
        uow=uow,
        audit=audit,
    )


def get_upload_user_avatar_use_case(
    user_repo: IUserRepository = Depends(get_user_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    link_repo: IUserPdmLinkRepository = Depends(get_user_pdm_link_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UploadUserAvatar:
    return UploadUserAvatar(user_repo=user_repo, storage=storage, link_repo=link_repo, uow=uow)


def get_delete_user_avatar_use_case(
    user_repo: IUserRepository = Depends(get_user_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    link_repo: IUserPdmLinkRepository = Depends(get_user_pdm_link_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> DeleteUserAvatar:
    return DeleteUserAvatar(user_repo=user_repo, storage=storage, link_repo=link_repo, uow=uow)


def get_user_avatar_use_case(
    user_repo: IUserRepository = Depends(get_user_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> GetUserAvatar:
    return GetUserAvatar(user_repo=user_repo, storage=storage, uow=uow)


def get_create_api_key_use_case(
    key_repo: IApiKeyRepository = Depends(get_api_key_repo),
    user_repo: IUserRepository = Depends(get_user_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    settings_repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    audit: SecurityAudit = Depends(get_security_audit),
) -> CreateApiKey:
    return CreateApiKey(
        key_repo=key_repo,
        user_repo=user_repo,
        uow=uow,
        settings_repo=settings_repo,
        hash_password_fn=aget_hash,
        audit=audit,
    )


def get_revoke_api_key_use_case(
    key_repo: IApiKeyRepository = Depends(get_api_key_repo),
    user_repo: IUserRepository = Depends(get_user_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    audit: SecurityAudit = Depends(get_security_audit),
) -> RevokeApiKey:
    return RevokeApiKey(key_repo=key_repo, user_repo=user_repo, uow=uow, audit=audit)


def get_revoke_all_api_keys_use_case(
    key_repo: IApiKeyRepository = Depends(get_api_key_repo),
    user_repo: IUserRepository = Depends(get_user_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    audit: SecurityAudit = Depends(get_security_audit),
) -> RevokeAllApiKeys:
    return RevokeAllApiKeys(key_repo=key_repo, user_repo=user_repo, uow=uow, audit=audit)


def get_create_pat_use_case(
    pat_repo: IPatRepository = Depends(get_pat_repo),
    settings_repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    password_confirmation: PasswordConfirmation = Depends(get_password_confirmation),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    audit: SecurityAudit = Depends(get_security_audit),
) -> CreatePatWithPassword:
    return CreatePatWithPassword(
        CreatePat(pat_repo=pat_repo, settings_repo=settings_repo, uow=uow, audit=audit),
        password_confirmation,
    )


def get_revoke_pat_use_case(
    pat_repo: IPatRepository = Depends(get_pat_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    audit: SecurityAudit = Depends(get_security_audit),
) -> RevokePat:
    return RevokePat(pat_repo=pat_repo, uow=uow, audit=audit)


def get_revoke_all_pats_use_case(
    pat_repo: IPatRepository = Depends(get_pat_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    audit: SecurityAudit = Depends(get_security_audit),
) -> RevokeAllPats:
    return RevokeAllPats(pat_repo=pat_repo, uow=uow, audit=audit)


def get_api_keys_use_case(
    key_repo: IApiKeyRepository = Depends(get_api_key_repo),
) -> GetApiKeys:
    return GetApiKeys(key_repo)


def get_api_key_use_case(
    key_repo: IApiKeyRepository = Depends(get_api_key_repo),
) -> GetApiKey:
    return GetApiKey(key_repo)


def get_api_key_usage_log_use_case(
    key_repo: IApiKeyRepository = Depends(get_api_key_repo),
    usage_log_repo: IApiKeyUsageLogRepository = Depends(get_api_key_usage_log_repo),
) -> GetApiKeyUsageLog:
    return GetApiKeyUsageLog(key_repo, usage_log_repo)


def get_pats_use_case(
    pat_repo: IPatRepository = Depends(get_pat_repo),
) -> GetPats:
    return GetPats(pat_repo)


def get_pat_use_case(
    pat_repo: IPatRepository = Depends(get_pat_repo),
) -> GetPat:
    return GetPat(pat_repo)


def get_pat_usage_log_use_case(
    pat_repo: IPatRepository = Depends(get_pat_repo),
    usage_log_repo: IPatUsageLogRepository = Depends(get_pat_usage_log_repo),
) -> GetPatUsageLog:
    return GetPatUsageLog(pat_repo, usage_log_repo)


# ── User groups ─────────────────────────────────────────────────────────


def get_list_user_groups_use_case(
    group_repo: IUserGroupRepository = Depends(get_user_group_repo),
) -> ListUserGroups:
    return ListUserGroups(group_repo)


def get_create_user_group_use_case(
    group_repo: IUserGroupRepository = Depends(get_user_group_repo),
    user_repo: IUserRepository = Depends(get_user_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    audit: SecurityAudit = Depends(get_security_audit),
) -> CreateUserGroup:
    return CreateUserGroup(group_repo, user_repo, event_bus=event_bus, uow=uow, audit=audit)


def get_update_user_group_use_case(
    group_repo: IUserGroupRepository = Depends(get_user_group_repo),
    user_repo: IUserRepository = Depends(get_user_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    audit: SecurityAudit = Depends(get_security_audit),
) -> UpdateUserGroup:
    return UpdateUserGroup(group_repo, user_repo, event_bus=event_bus, uow=uow, audit=audit)


def get_delete_user_group_use_case(
    group_repo: IUserGroupRepository = Depends(get_user_group_repo),
    user_repo: IUserRepository = Depends(get_user_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    audit: SecurityAudit = Depends(get_security_audit),
) -> DeleteUserGroup:
    return DeleteUserGroup(group_repo, user_repo, event_bus=event_bus, uow=uow, audit=audit)
