"""
AdminSettingsMapper, the single entry point callers use, composed from the
per-group mappers in this package. The groups share no methods, so the
base class order carries no meaning.
"""

from src.modules.catalogue.application.mappers.admin_settings_mapper.data_import import (
    DataImportSettingsMapper,
)
from src.modules.catalogue.application.mappers.admin_settings_mapper.made_items import (
    MadeItemSettingsMapper,
)
from src.modules.catalogue.application.mappers.admin_settings_mapper.orders import (
    OrderSettingsMapper,
)
from src.modules.external_data.application.mappers.admin_settings_mapper.eplan_data_portal import (
    EdpSettingsMapper,
)
from src.modules.external_data.application.mappers.admin_settings_mapper.pdm import (
    PdmSettingsMapper,
)
from src.modules.external_data.application.mappers.admin_settings_mapper.pdm_vault import (
    PdmVaultMapper,
)
from src.modules.external_data.application.mappers.admin_settings_mapper.stock import (
    StockSettingsMapper,
)
from src.modules.fulfillment.application.mappers.admin_settings_mapper.production import (
    ProductionSettingsMapper,
)
from src.modules.operations.application.mappers.admin_settings_mapper.time_tracking import (
    TimeTrackingSettingsMapper,
)
from src.modules.platform.application.mappers.admin_settings_mapper.audit import AuditEntryMapper
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


class AdminSettingsMapper(
    HostSettingsMapper,
    MailSettingsMapper,
    AuthSettingsMapper,
    StorageSettingsMapper,
    SecuritySettingsMapper,
    FeatureSettingsMapper,
    GeneralSettingsMapper,
    BrandingSettingsMapper,
    NotificationSettingsMapper,
    MaintenanceSettingsMapper,
    BannerSettingsMapper,
    RetentionSettingsMapper,
    OrderSettingsMapper,
    MadeItemSettingsMapper,
    PdmSettingsMapper,
    PdmVaultMapper,
    ProductionSettingsMapper,
    TimeTrackingSettingsMapper,
    DataImportSettingsMapper,
    EdpSettingsMapper,
    StockSettingsMapper,
    AuditEntryMapper,
):
    """Converts admin settings domain entities to result DTOs."""
