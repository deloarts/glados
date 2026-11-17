"""
The public API of CAD & external data: its settings port and the CAD provider port.

Other modules reach this module through this file and its named interfaces:
the domain entities, events, value objects, errors and policies
(`domain/policies/`), the DTOs (`application/dto/`), the query facades
(`application/facade/`), the ports outside `ports/outbound/repositories/`
(the query ports among them) and the settings store. Everything else is internal, which the
module's protected contract in backend/.importlinter enforces.
"""

from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)

__all__ = [
    "IExternalDataSettingsRepository",
]
