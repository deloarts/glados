"""
Commands and results for the AI agent settings.
"""

from datetime import datetime

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator

from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.domain.entities.admin_settings.agents import APPROVED_PROVIDERS_MAX_LENGTH
from src.modules.platform.domain.entities.admin_settings.agents import normalize_ai_policy_url
from src.modules.platform.domain.services.agent_policy import normalise_allowed_origins


class UpdateAgentSettingsCommand(BaseModel):
    enabled: bool = False
    token_max_lifetime_days: int = Field(default=30, ge=1, le=365)
    token_idle_revoke_days: int = Field(default=14, ge=1, le=365)
    include_person_names: bool = False
    include_costs: bool = False
    allowed_origins: list[str] = []
    calls_per_minute: int = Field(default=120, ge=1, le=10000)
    drafts_per_hour: int = Field(default=20, ge=0, le=1000)
    processing_approved: bool = False
    approved_providers: str = Field(default="", max_length=APPROVED_PROVIDERS_MAX_LENGTH)
    ai_policy_url: str | None = None

    @field_validator("allowed_origins")
    @classmethod
    def validate_allowed_origins(cls, v: list[str]) -> list[str]:
        return normalise_allowed_origins(v)

    @field_validator("approved_providers")
    @classmethod
    def strip_approved_providers(cls, v: str) -> str:
        return v.strip()

    @field_validator("ai_policy_url")
    @classmethod
    def validate_ai_policy_url(cls, v: str | None) -> str | None:
        return normalize_ai_policy_url(v)


class AdminAgentSettingsResult(ResultBase):
    enabled: bool
    token_max_lifetime_days: int
    token_idle_revoke_days: int
    include_person_names: bool
    include_costs: bool
    allowed_origins: list[str]
    calls_per_minute: int
    drafts_per_hour: int
    approved_providers: str
    ai_policy_url: str | None
    processing_approved_at: datetime | None
