"""
Whether the PDM integration is on, which the read tier's capabilities and
numbering routes report so forms can present PDM-owned inputs and number
spaces correctly.
"""

from src.modules.external_data.application.services.pdm_integration import is_pdm_enabled

__all__ = ["is_pdm_enabled"]
