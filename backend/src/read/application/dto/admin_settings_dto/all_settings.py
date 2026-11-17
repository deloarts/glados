"""
Result DTO aggregating every admin settings group in one payload.
"""

from pydantic import BaseModel

from src.modules.catalogue.application.dto.admin_settings_dto.made_items import (
    AdminMadeItemSettingsResult,
)
from src.modules.catalogue.application.dto.admin_settings_dto.orders import AdminOrderSettingsResult
from src.modules.external_data.application.dto.admin_settings_dto.pdm import AdminPdmSettingsResult
from src.modules.fulfillment.application.dto.admin_settings_dto.production import (
    AdminProductionSettingsResult,
)
from src.modules.platform.application.dto.admin_settings_dto.auth import AdminAuthSettingsResult
from src.modules.platform.application.dto.admin_settings_dto.banner import AdminBannerSettingsResult
from src.modules.platform.application.dto.admin_settings_dto.branding import (
    AdminBrandingSettingsResult,
)
from src.modules.platform.application.dto.admin_settings_dto.features import (
    AdminFeatureSettingsResult,
)
from src.modules.platform.application.dto.admin_settings_dto.general import (
    AdminGeneralSettingsResult,
)
from src.modules.platform.application.dto.admin_settings_dto.host import AdminHostSettingsResult
from src.modules.platform.application.dto.admin_settings_dto.mail import AdminMailSettingsResult
from src.modules.platform.application.dto.admin_settings_dto.maintenance import (
    AdminMaintenanceSettingsResult,
)
from src.modules.platform.application.dto.admin_settings_dto.notifications import (
    AdminNotificationSettingsResult,
)
from src.modules.platform.application.dto.admin_settings_dto.retention import (
    AdminRetentionSettingsResult,
)
from src.modules.platform.application.dto.admin_settings_dto.security import (
    AdminSecuritySettingsResult,
)
from src.modules.platform.application.dto.admin_settings_dto.storage import (
    AdminStorageSettingsResult,
)


class AllAdminSettingsResult(BaseModel):
    host: AdminHostSettingsResult
    mail: AdminMailSettingsResult
    auth: AdminAuthSettingsResult
    storage: AdminStorageSettingsResult
    security: AdminSecuritySettingsResult
    features: AdminFeatureSettingsResult
    general: AdminGeneralSettingsResult
    branding: AdminBrandingSettingsResult
    notifications: AdminNotificationSettingsResult
    maintenance: AdminMaintenanceSettingsResult
    retention: AdminRetentionSettingsResult
    orders: AdminOrderSettingsResult
    made_items: AdminMadeItemSettingsResult
    production: AdminProductionSettingsResult
    banner: AdminBannerSettingsResult
    pdm: AdminPdmSettingsResult
