"""
Converts between PersonalAccessToken/PatUsageLogEntry domain entities and DTOs.
"""

from src.modules.platform.application.dto.pat_dto import CreatedPatResult
from src.modules.platform.application.dto.pat_dto import PatResult
from src.modules.platform.application.dto.pat_dto import PatUsageLogEntryResult
from src.modules.platform.domain.entities.pat_usage_log import PatUsageLogEntry
from src.modules.platform.domain.entities.personal_access_token import PersonalAccessToken


class PatMapper:
    @staticmethod
    def to_result(token: PersonalAccessToken) -> PatResult:
        return PatResult(
            id=token.id,
            public_id=token.public_id,
            name=token.name,
            token_prefix=token.token_prefix,
            permissions=token.permissions,
            created=token.created,
            expires_at=token.expires_at,
            revoked_at=token.revoked_at,
            is_expired=token.is_expired,
        )

    @staticmethod
    def to_created_result(token: PersonalAccessToken, raw_token: str) -> CreatedPatResult:
        return CreatedPatResult(
            id=token.id,
            public_id=token.public_id,
            name=token.name,
            token_prefix=token.token_prefix,
            permissions=token.permissions,
            created=token.created,
            expires_at=token.expires_at,
            revoked_at=token.revoked_at,
            is_expired=token.is_expired,
            token=raw_token,
        )

    @staticmethod
    def usage_to_result(entry: PatUsageLogEntry) -> PatUsageLogEntryResult:
        return PatUsageLogEntryResult(
            id=entry.id,
            public_id=entry.public_id,
            pat_id=entry.pat_id,
            called_at=entry.called_at,
            method=entry.method,
            path=entry.path,
            status_code=entry.status_code,
        )
