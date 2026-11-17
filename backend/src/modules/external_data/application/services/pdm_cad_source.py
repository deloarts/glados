"""
SolidWorks PDM as Catalogue's CAD source: the CAD policy Catalogue's item use
cases follow, read from the PDM settings.
"""

from src.modules.catalogue.api import CadPolicy
from src.modules.external_data.api import IExternalDataSettingsRepository
from src.modules.external_data.application.services.pdm_integration import is_pdm_enabled


class PdmCadSource:
    """ICadSource over the PDM settings."""

    def __init__(self, settings: IExternalDataSettingsRepository) -> None:
        self._settings = settings

    async def policy(self) -> CadPolicy:
        pdm = await self._settings.get_pdm()
        connected = is_pdm_enabled(pdm)
        return CadPolicy(connected=connected, rows_read_only=connected and pdm.cad_items_read_only)
