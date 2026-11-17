"""
Result DTO for the Host tab's overview of which integrations are switched on
and configured.
"""

from typing import Literal

from pydantic import BaseModel

# "active": switched on and everything it needs is set. "incomplete":
# switched on, but a connection detail, a key or a prerequisite is missing,
# so it does nothing yet. "off": switched off.
IntegrationState = Literal["active", "incomplete", "off"]


class IntegrationStatusResult(BaseModel):
    key: str  # stable key the frontend labels and links to its settings tab
    state: IntegrationState


class IntegrationsOverviewResult(BaseModel):
    integrations: list[IntegrationStatusResult]
