"""Use case factories: the admin settings tabs (general, host, branding, mail,
numbering, notifications, security, auth, features, maintenance,
retention, storage, audit, security log) and the public login background
video.
"""

from fastapi import Depends

from src.modules.platform.adapters.inbound.api.deps.bindings import get_schedule_recompute
from src.modules.platform.adapters.inbound.api.deps.bindings import get_service_health_checker
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.adapters.inbound.api.deps.repositories import get_platform_settings_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_security_event_repo
from src.modules.platform.adapters.inbound.api.deps.services import get_ldap_authenticator_factory
from src.modules.platform.adapters.inbound.api.deps.services import get_mail_service
from src.modules.platform.adapters.inbound.api.deps.services import get_optional_storage_adapter
from src.modules.platform.adapters.inbound.api.deps.services import get_storage_adapter_factory
from src.modules.platform.adapters.inbound.api.deps.services import get_system_stats_reader
from src.modules.platform.adapters.outbound.external.mail.render import render_string
from src.modules.platform.application.services.schedule_recompute_port import ScheduleRecompute
from src.modules.platform.application.use_cases.admin_settings.delete_branding_favicon import (
    DeleteBrandingFavicon,
)
from src.modules.platform.application.use_cases.admin_settings.delete_branding_logo import (
    DeleteBrandingLogo,
)
from src.modules.platform.application.use_cases.admin_settings.delete_company_logo import (
    DeleteCompanyLogo,
)
from src.modules.platform.application.use_cases.admin_settings.delete_login_background_video import (
    DeleteLoginBackgroundVideo,
)
from src.modules.platform.application.use_cases.admin_settings.get_admin_settings import (
    GetAdminSettingsAudit,
)
from src.modules.platform.application.use_cases.admin_settings.get_agent_settings import (
    GetAgentSettings,
)
from src.modules.platform.application.use_cases.admin_settings.get_auth_settings import (
    GetAuthSettings,
)
from src.modules.platform.application.use_cases.admin_settings.get_banner_settings import (
    GetBannerSettings,
)
from src.modules.platform.application.use_cases.admin_settings.get_branding_settings import (
    GetBrandingSettings,
)
from src.modules.platform.application.use_cases.admin_settings.get_feature_settings import (
    GetFeatureSettings,
)
from src.modules.platform.application.use_cases.admin_settings.get_general_settings import (
    GetGeneralSettings,
)
from src.modules.platform.application.use_cases.admin_settings.get_host_settings import (
    GetHostSettings,
)
from src.modules.platform.application.use_cases.admin_settings.get_host_stats import GetHostStats
from src.modules.platform.application.use_cases.admin_settings.get_login_background_video import (
    GetLoginBackgroundVideo,
)
from src.modules.platform.application.use_cases.admin_settings.get_mail_settings import (
    GetMailSettings,
)
from src.modules.platform.application.use_cases.admin_settings.get_mail_templates import (
    GetMailTemplates,
)
from src.modules.platform.application.use_cases.admin_settings.get_maintenance_settings import (
    GetMaintenanceSettings,
)
from src.modules.platform.application.use_cases.admin_settings.get_notification_settings import (
    GetNotificationSettings,
)
from src.modules.platform.application.use_cases.admin_settings.get_retention_settings import (
    GetRetentionSettings,
)
from src.modules.platform.application.use_cases.admin_settings.get_security_settings import (
    GetSecuritySettings,
)
from src.modules.platform.application.use_cases.admin_settings.get_services_health import (
    GetServicesHealth,
)
from src.modules.platform.application.use_cases.admin_settings.get_storage_settings import (
    GetStorageSettings,
)
from src.modules.platform.application.use_cases.admin_settings.get_web_app_manifest import (
    GetWebAppManifest,
)
from src.modules.platform.application.use_cases.admin_settings.preview_mail_template import (
    PreviewMailTemplate,
)
from src.modules.platform.application.use_cases.admin_settings.send_test_mail import SendTestMail
from src.modules.platform.application.use_cases.admin_settings.test_storage_connection import (
    TestStorageConnection,
)
from src.modules.platform.application.use_cases.admin_settings.update_agent_settings import (
    UpdateAgentSettings,
)
from src.modules.platform.application.use_cases.admin_settings.update_auth_settings import (
    UpdateAuthSettings,
)
from src.modules.platform.application.use_cases.admin_settings.update_banner_settings import (
    UpdateBannerSettings,
)
from src.modules.platform.application.use_cases.admin_settings.update_branding_settings import (
    UpdateBrandingSettings,
)
from src.modules.platform.application.use_cases.admin_settings.update_feature_settings import (
    UpdateFeatureSettings,
)
from src.modules.platform.application.use_cases.admin_settings.update_general_settings import (
    UpdateGeneralSettings,
)
from src.modules.platform.application.use_cases.admin_settings.update_mail_settings import (
    UpdateMailSettings,
)
from src.modules.platform.application.use_cases.admin_settings.update_mail_templates import (
    UpdateMailTemplates,
)
from src.modules.platform.application.use_cases.admin_settings.update_maintenance_settings import (
    UpdateMaintenanceSettings,
)
from src.modules.platform.application.use_cases.admin_settings.update_notification_settings import (
    UpdateNotificationSettings,
)
from src.modules.platform.application.use_cases.admin_settings.update_retention_settings import (
    UpdateRetentionSettings,
)
from src.modules.platform.application.use_cases.admin_settings.update_security_settings import (
    UpdateSecuritySettings,
)
from src.modules.platform.application.use_cases.admin_settings.update_storage_settings import (
    UpdateStorageSettings,
)
from src.modules.platform.application.use_cases.admin_settings.upload_branding_favicon import (
    UploadBrandingFavicon,
)
from src.modules.platform.application.use_cases.admin_settings.upload_branding_logo import (
    UploadBrandingLogo,
)
from src.modules.platform.application.use_cases.admin_settings.upload_company_logo import (
    UploadCompanyLogo,
)
from src.modules.platform.application.use_cases.admin_settings.upload_login_background_video import (
    UploadLoginBackgroundVideo,
)
from src.modules.platform.application.use_cases.admin_settings.verify_ldap_connection import (
    VerifyLdapConnection,
)
from src.modules.platform.application.use_cases.security_event.list_security_events import (
    ListSecurityEvents,
)
from src.modules.platform.infrastructure.config.settings import cfg
from src.modules.platform.ports.outbound.ldap_authenticator_port import ILdapAuthenticatorFactory
from src.modules.platform.ports.outbound.mail_service_port import IMailService
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.repositories.security_event_repository import (
    ISecurityEventRepository,
)
from src.modules.platform.ports.outbound.service_health_port import IServiceHealthChecker
from src.modules.platform.ports.outbound.storage_port import IStorageAdapterFactory
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.system_stats_port import ISystemStatsReader
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


def get_auth_settings_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
) -> GetAuthSettings:
    return GetAuthSettings(repo)


def get_update_auth_settings_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateAuthSettings:
    return UpdateAuthSettings(repo, uow=uow)


def get_verify_ldap_connection_use_case(
    ldap_factory: ILdapAuthenticatorFactory = Depends(get_ldap_authenticator_factory),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> VerifyLdapConnection:
    return VerifyLdapConnection(ldap_factory, uow=uow)


def get_admin_settings_audit_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
) -> GetAdminSettingsAudit:
    return GetAdminSettingsAudit(repo)


def get_list_security_events_use_case(
    repo: ISecurityEventRepository = Depends(get_security_event_repo),
) -> ListSecurityEvents:
    return ListSecurityEvents(repo)


def get_feature_settings_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
) -> GetFeatureSettings:
    return GetFeatureSettings(repo)


def get_update_feature_settings_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateFeatureSettings:
    return UpdateFeatureSettings(repo, uow=uow)


def get_maintenance_settings_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
) -> GetMaintenanceSettings:
    return GetMaintenanceSettings(repo)


def get_update_maintenance_settings_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateMaintenanceSettings:
    return UpdateMaintenanceSettings(repo, uow=uow)


def get_retention_settings_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
) -> GetRetentionSettings:
    return GetRetentionSettings(repo)


def get_update_retention_settings_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateRetentionSettings:
    return UpdateRetentionSettings(repo, uow=uow)


def get_security_settings_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
) -> GetSecuritySettings:
    return GetSecuritySettings(repo)


def get_update_security_settings_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateSecuritySettings:
    return UpdateSecuritySettings(repo, uow=uow)


def get_agent_settings_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
) -> GetAgentSettings:
    return GetAgentSettings(repo)


def get_update_agent_settings_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateAgentSettings:
    return UpdateAgentSettings(repo, uow=uow)


def get_notification_settings_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
) -> GetNotificationSettings:
    return GetNotificationSettings(repo)


def get_update_notification_settings_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateNotificationSettings:
    return UpdateNotificationSettings(repo, uow=uow)


def get_banner_settings_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
) -> GetBannerSettings:
    return GetBannerSettings(repo)


def get_update_banner_settings_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateBannerSettings:
    return UpdateBannerSettings(repo, uow=uow)


def get_host_settings_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
) -> GetHostSettings:
    return GetHostSettings(repo, cfg.domain)


def get_host_stats_use_case(
    reader: ISystemStatsReader = Depends(get_system_stats_reader),
) -> GetHostStats:
    return GetHostStats(reader, cfg.domain)


def get_services_health_use_case(
    checker: IServiceHealthChecker = Depends(get_service_health_checker),
) -> GetServicesHealth:
    return GetServicesHealth(checker)


def get_general_settings_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
) -> GetGeneralSettings:
    return GetGeneralSettings(repo)


def get_update_general_settings_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    recompute: ScheduleRecompute = Depends(get_schedule_recompute),
) -> UpdateGeneralSettings:
    return UpdateGeneralSettings(repo, uow=uow, recompute_schedule=recompute)


def get_upload_company_logo_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UploadCompanyLogo:
    return UploadCompanyLogo(repo, storage, uow=uow)


def get_delete_company_logo_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
) -> DeleteCompanyLogo:
    return DeleteCompanyLogo(repo, storage, uow=uow)


def get_mail_settings_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
) -> GetMailSettings:
    return GetMailSettings(repo)


def get_update_mail_settings_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateMailSettings:
    return UpdateMailSettings(repo, uow=uow)


def get_send_test_mail_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    mail_service: IMailService = Depends(get_mail_service),
) -> SendTestMail:
    return SendTestMail(settings_repo=repo, mail_service=mail_service)


def get_mail_templates_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
) -> GetMailTemplates:
    return GetMailTemplates(repo)


def get_update_mail_templates_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateMailTemplates:
    return UpdateMailTemplates(repo, uow=uow)


def get_preview_mail_template_use_case() -> PreviewMailTemplate:
    return PreviewMailTemplate(render_string)


def get_branding_settings_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
) -> GetBrandingSettings:
    return GetBrandingSettings(repo)


def get_update_branding_settings_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateBrandingSettings:
    return UpdateBrandingSettings(repo, uow=uow)


def get_upload_login_background_video_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UploadLoginBackgroundVideo:
    return UploadLoginBackgroundVideo(repo, storage, uow=uow)


def get_delete_login_background_video_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
) -> DeleteLoginBackgroundVideo:
    return DeleteLoginBackgroundVideo(repo, storage, uow=uow)


def get_upload_branding_logo_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UploadBrandingLogo:
    return UploadBrandingLogo(repo, storage, uow=uow)


def get_delete_branding_logo_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
) -> DeleteBrandingLogo:
    return DeleteBrandingLogo(repo, storage, uow=uow)


def get_upload_branding_favicon_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UploadBrandingFavicon:
    return UploadBrandingFavicon(repo, storage, uow=uow)


def get_delete_branding_favicon_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
) -> DeleteBrandingFavicon:
    return DeleteBrandingFavicon(repo, storage, uow=uow)


def get_storage_settings_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
) -> GetStorageSettings:
    return GetStorageSettings(repo)


def get_update_storage_settings_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateStorageSettings:
    return UpdateStorageSettings(repo, uow=uow)


def get_test_storage_connection_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    storage_factory: IStorageAdapterFactory = Depends(get_storage_adapter_factory),
) -> TestStorageConnection:
    return TestStorageConnection(repo, storage_factory)


def get_login_background_video_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> GetLoginBackgroundVideo:
    return GetLoginBackgroundVideo(repo, storage, uow)


def get_web_app_manifest_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> GetWebAppManifest:
    return GetWebAppManifest(repo, storage, uow)
