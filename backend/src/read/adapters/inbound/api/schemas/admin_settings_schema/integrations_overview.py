"""
Response schema for the Host tab's overview of which integrations are
switched on and configured.
"""

from typing import Literal

from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel


class IntegrationStatusResponse(ResponseModel):
    key: str
    state: Literal["active", "incomplete", "off"]


class IntegrationsOverviewResponse(ResponseModel):
    integrations: list[IntegrationStatusResponse]
