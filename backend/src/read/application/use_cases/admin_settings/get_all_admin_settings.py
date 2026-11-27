"""
Every admin settings section in one response, for the settings page. It
reads the sections of every module, so it sits in the read tier. Requires
read:settings permission.
"""

from src.modules.catalogue.application.mappers.admin_settings_mapper.made_items import (
    MadeItemSettingsMapper,
)
from src.modules.catalogue.application.mappers.admin_settings_mapper.orders import (
    OrderSettingsMapper,
)
from src.modules.external_data.application.mappers.admin_settings_mapper.pdm import (
    PdmSettingsMapper,
)
from src.modules.fulfillment.application.mappers.admin_settings_mapper.planning import (
    PlanningSettingsMapper,
)
from src.modules.fulfillment.application.mappers.admin_settings_mapper.production import (
    ProductionSettingsMapper,
)
from src.modules.platform.application.mappers.admin_settings_mapper.auth import AuthSettingsMapper
from src.modules.platform.application.mappers.admin_settings_mapper.banner import (
    BannerSettingsMapper,
)
from src.modules.platform.application.mappers.admin_settings_mapper.branding import (
    BrandingSettingsMapper,
)
from src.modules.platform.application.mappers.admin_settings_mapper.features import (
    FeatureSettingsMapper,
)
from src.modules.platform.application.mappers.admin_settings_mapper.general import (
    GeneralSettingsMapper,
)
from src.modules.platform.application.mappers.admin_settings_mapper.host import HostSettingsMapper
from src.modules.platform.application.mappers.admin_settings_mapper.mail import MailSettingsMapper
from src.modules.platform.application.mappers.admin_settings_mapper.maintenance import (
    MaintenanceSettingsMapper,
)
from src.modules.platform.application.mappers.admin_settings_mapper.notifications import (
    NotificationSettingsMapper,
)
from src.modules.platform.application.mappers.admin_settings_mapper.retention import (
    RetentionSettingsMapper,
)
from src.modules.platform.application.mappers.admin_settings_mapper.security import (
    SecuritySettingsMapper,
)
from src.modules.platform.application.mappers.admin_settings_mapper.storage import (
    StorageSettingsMapper,
)
from src.modules.platform.application.services.tenant_timezone import tenant_zone
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.read.application.dto.admin_settings_dto.all_settings import AllAdminSettingsResult
from src.read.ports.outbound.repositories.admin_settings_repository import IAdminSettingsRepository
from src.shared_kernel.domain.services.clock import today_in


class GetAllAdminSettings:
    def __init__(
        self,
        repo: IAdminSettingsRepository,
        domain: str,
        *,
        pdm_mutating_operations_enabled: bool = False,
    ) -> None:
        self._repo = repo
        self._domain = domain
        self._pdm_mutating_operations_enabled = pdm_mutating_operations_enabled

    async def execute(self, actor: User) -> AllAdminSettingsResult:
        SettingsRules.assert_can_read(actor)
        today = today_in(await tenant_zone(self._repo))
        return AllAdminSettingsResult(
            host=HostSettingsMapper.host_to_result(await self._repo.get_host(), self._domain),
            mail=MailSettingsMapper.mail_to_result(await self._repo.get_mail()),
            auth=AuthSettingsMapper.auth_to_result(await self._repo.get_auth()),
            storage=StorageSettingsMapper.storage_to_result(await self._repo.get_storage()),
            security=SecuritySettingsMapper.security_to_result(await self._repo.get_security()),
            features=FeatureSettingsMapper.features_to_result(await self._repo.get_features()),
            general=GeneralSettingsMapper.general_to_result(await self._repo.get_general()),
            branding=BrandingSettingsMapper.branding_to_result(await self._repo.get_branding()),
            notifications=NotificationSettingsMapper.notifications_to_result(
                await self._repo.get_notifications()
            ),
            maintenance=MaintenanceSettingsMapper.maintenance_to_result(
                await self._repo.get_maintenance()
            ),
            retention=RetentionSettingsMapper.retention_to_result(await self._repo.get_retention()),
            orders=OrderSettingsMapper.orders_to_result(await self._repo.get_orders(), today=today),
            made_items=MadeItemSettingsMapper.made_items_to_result(
                await self._repo.get_made_items(), today=today
            ),
            production=ProductionSettingsMapper.production_to_result(
                await self._repo.get_production(), today=today
            ),
            planning=PlanningSettingsMapper.planning_to_result(await self._repo.get_planning()),
            banner=BannerSettingsMapper.banner_to_result(await self._repo.get_banner()),
            pdm=PdmSettingsMapper.pdm_to_result(
                await self._repo.get_pdm(),
                mutating_operations_enabled=self._pdm_mutating_operations_enabled,
            ),
        )
