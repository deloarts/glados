"""
The public API of Platform: the settings port every module extends and the
ports Platform code calls that other modules implement. The hooks other
modules plug into, such as the notification rules, the schedule walk and the
transaction listener, are in Platform's application services, which are a
named interface too.

Other modules reach this module through this file and its named interfaces:
the domain entities, events, value objects, errors and policies
(`domain/policies/`), the DTOs (`application/dto/`), the query facades
(`application/facade/`), the ports outside `ports/outbound/repositories/`
(the query ports among them) and the settings store. Everything else is internal, which the
module's protected contract in backend/.importlinter enforces.
"""

from src.modules.platform.ports.outbound.platform_settings_repository import (
    AdminSettingsAuditFilterDto,
)
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.repositories.tenant_holiday_repository import (
    ITenantHolidayRepository,
)
from src.modules.platform.ports.outbound.user_held_credentials_port import IUserHeldCredentials

__all__ = [
    "AdminSettingsAuditFilterDto",
    "IPlatformSettingsRepository",
    "ITenantHolidayRepository",
    "IUserHeldCredentials",
]
