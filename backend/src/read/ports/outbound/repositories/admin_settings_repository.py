"""
The whole admin settings record: every module's settings sections and the
settings audit log, for the readers that span them (the settings page's
aggregate, the host overview) and the composition root. Platform's own
sections are in platform_settings_repository.py, and each module extends
them with its own sections in its settings port, so a module's code sees
its own settings and those of the modules it depends on.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.operations.ports.outbound.operations_settings_repository import (
    IOperationsSettingsRepository,
)
from src.modules.platform.ports.outbound.platform_settings_repository import (
    AdminSettingsAuditFilterDto as AdminSettingsAuditFilterDto,
)


@runtime_checkable
class IAdminSettingsRepository(
    IExternalDataSettingsRepository, IOperationsSettingsRepository, Protocol
):
    """The union of every module's settings port."""
