"""
The settings store the composition root wires: every module's settings
sections in one SQLAlchemy repository, assembled from the stores each module
owns (platform_settings_repository.py and the module settings stores next
to it).
"""

from src.modules.external_data.adapters.outbound.persistence.repositories.external_data_settings_repository import (
    SqlAlchemyExternalDataSettingsRepository,
)
from src.modules.operations.adapters.outbound.persistence.repositories.operations_settings_repository import (
    SqlAlchemyOperationsSettingsRepository,
)
from src.read.ports.outbound.repositories.admin_settings_repository import IAdminSettingsRepository


class SqlAlchemyAdminSettingsRepository(
    SqlAlchemyExternalDataSettingsRepository,
    SqlAlchemyOperationsSettingsRepository,
    IAdminSettingsRepository,
):
    """Every module's settings sections and the settings audit log."""
