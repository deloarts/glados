"""
A user's confirmation that their AI agent may process Glados data on their
behalf. A personal access token reaches the MCP surface only while its
owner's confirmation is current, so a user decides for themselves, in
addition to the permission an admin grants and the company's approval in
the agent settings. Withdrawing deletes the row.
"""

from dataclasses import dataclass
from datetime import datetime

from src.shared_kernel.domain.entities.base import Entity


@dataclass
class AgentConsent(Entity):
    user_id: int
    # The version of the consent text the user confirmed.
    consent_version: int
    consented_at: datetime  # UTC, aware
