"""
The public API of Catalogue: its settings port, which the modules above it extend,
the CAD source and CAD file link ports, which CAD & external data
implements, the contact copies port, which Workspace implements, and two ports
Planning & fulfillment answers as it is: the default machine lookup (its
machine repository) and the inspection method usage (its settings store).

Other modules reach this module through this file and its named interfaces:
the domain entities, events, value objects, errors and policies
(`domain/policies/`), the DTOs (`application/dto/`), the query facades
(`application/facade/`), the ports outside `ports/outbound/repositories/`
(the query ports among them) and the settings store. Everything else is internal, which the
module's protected contract in backend/.importlinter enforces.
"""

from src.modules.catalogue.ports.outbound.cad_file_link_port import ICadFileLinks
from src.modules.catalogue.ports.outbound.cad_source_port import CadPolicy
from src.modules.catalogue.ports.outbound.cad_source_port import ICadSource
from src.modules.catalogue.ports.outbound.catalogue_settings_repository import (
    ICatalogueSettingsRepository,
)
from src.modules.catalogue.ports.outbound.contact_copies_port import IContactCopies
from src.modules.catalogue.ports.outbound.default_machine_port import DefaultMachineCandidate
from src.modules.catalogue.ports.outbound.default_machine_port import IDefaultMachineLookup
from src.modules.catalogue.ports.outbound.inspection_method_usage_port import IInspectionMethodUsage
from src.modules.catalogue.ports.outbound.inspection_method_usage_port import ProductionQaDefault

__all__ = [
    "CadPolicy",
    "DefaultMachineCandidate",
    "ICadFileLinks",
    "ICadSource",
    "ICatalogueSettingsRepository",
    "IContactCopies",
    "IDefaultMachineLookup",
    "IInspectionMethodUsage",
    "ProductionQaDefault",
]
