"""HTTP schemas for the agent call log and the caller's agent consent."""

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator

from src.modules.platform.application.dto.agent_dto import AgentCallResult
from src.modules.platform.application.dto.agent_dto import AgentConsentStatusResult
from src.modules.platform.application.dto.agent_dto import AgentCreatedRecordResult

__all__ = [
    "AgentCallResult",
    "AgentConsentStatusResult",
    "AgentCreatedRecordResult",
    "FindAgentCreatedRecordsRequest",
    "GiveAgentConsentRequest",
]


class GiveAgentConsentRequest(BaseModel):
    # The version of the consent text the user read, as the status returned
    # it; a different version is refused.
    consent_version: int


class FindAgentCreatedRecordsRequest(BaseModel):
    # The records of one list page, each as `<kind>:<public id>`.
    refs: list[str] = Field(max_length=200)

    @field_validator("refs")
    @classmethod
    def validate_refs(cls, v: list[str]) -> list[str]:
        for ref in v:
            if len(ref) > 80:
                raise ValueError("A reference is at most 80 characters long.")
        return v
