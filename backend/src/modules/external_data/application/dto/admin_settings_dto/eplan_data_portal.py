"""
Commands and results for the EPLAN Data Portal settings and the connection
test. None in an update keeps the stored value; for the token an empty
string clears it. The token itself is never part of a result.
"""

from pydantic import BaseModel

from src.modules.platform.application.dto.base import ResultBase


class UpdateEdpSettingsCommand(BaseModel):
    enabled: bool | None = None
    base_url: str | None = None
    pat: str | None = None
    default_article_group_ids: list[int] | None = None
    language: str | None = None


class VerifyEdpConnectionCommand(BaseModel):
    # None tests the stored value, so the admin can test before saving.
    base_url: str | None = None
    pat: str | None = None


class AdminEdpSettingsResult(ResultBase):
    enabled: bool
    base_url: str
    pat_configured: bool
    default_article_group_ids: list[int]
    language: str
    is_configured: bool


class EdpConnectionTestResult(BaseModel):
    authenticated: bool
