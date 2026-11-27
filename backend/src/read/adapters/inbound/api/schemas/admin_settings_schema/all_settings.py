"""
Response schema aggregating every admin settings group in one payload.
"""

from pydantic import ConfigDict

from src.modules.catalogue.adapters.inbound.api.schemas.admin_settings_schema.made_items import (
    AdminMadeItemSettingsResponse,
)
from src.modules.catalogue.adapters.inbound.api.schemas.admin_settings_schema.orders import (
    AdminOrderSettingsResponse,
)
from src.modules.external_data.adapters.inbound.api.schemas.admin_settings_schema.pdm import (
    AdminPdmSettingsResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.admin_settings_schema.planning import (
    AdminPlanningSettingsResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.admin_settings_schema.production import (
    AdminProductionSettingsResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.auth import (
    AdminAuthSettingsResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.banner import (
    AdminBannerSettingsResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.branding import (
    AdminBrandingSettingsResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.features import (
    AdminFeatureSettingsResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.general import (
    AdminGeneralSettingsResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.host import (
    AdminHostSettingsResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.mail import (
    AdminMailSettingsResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.maintenance import (
    AdminMaintenanceSettingsResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.notifications import (
    AdminNotificationSettingsResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.retention import (
    AdminRetentionSettingsResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.security import (
    AdminSecuritySettingsResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.storage import (
    AdminStorageSettingsResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel


class AllAdminSettingsResponse(ResponseModel):
    host: AdminHostSettingsResponse
    mail: AdminMailSettingsResponse
    auth: AdminAuthSettingsResponse
    storage: AdminStorageSettingsResponse
    security: AdminSecuritySettingsResponse
    features: AdminFeatureSettingsResponse
    general: AdminGeneralSettingsResponse
    branding: AdminBrandingSettingsResponse
    notifications: AdminNotificationSettingsResponse
    maintenance: AdminMaintenanceSettingsResponse
    retention: AdminRetentionSettingsResponse
    orders: AdminOrderSettingsResponse
    made_items: AdminMadeItemSettingsResponse
    production: AdminProductionSettingsResponse
    planning: AdminPlanningSettingsResponse
    banner: AdminBannerSettingsResponse
    pdm: AdminPdmSettingsResponse

    model_config = ConfigDict(from_attributes=True)
