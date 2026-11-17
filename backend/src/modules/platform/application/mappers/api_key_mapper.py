"""
Converts between ApiKey/ApiKeyUsageLogEntry domain entities and DTOs.
"""

from src.modules.platform.application.dto.api_key_dto import ApiKeyResult
from src.modules.platform.application.dto.api_key_dto import ApiKeyUsageLogEntryResult
from src.modules.platform.application.dto.api_key_dto import CreatedApiKeyResult
from src.modules.platform.domain.entities.api_key import ApiKey
from src.modules.platform.domain.entities.api_key_usage_log import ApiKeyUsageLogEntry


class ApiKeyMapper:
    @staticmethod
    def to_result(key: ApiKey) -> ApiKeyResult:
        return ApiKeyResult(
            id=key.id,
            public_id=key.public_id,
            name=key.name,
            token_prefix=key.token_prefix,
            permissions=key.permissions,
            created_by_id=key.created_by_id,
            created=key.created,
            expires_at=key.expires_at,
            revoked_at=key.revoked_at,
            is_expired=key.is_expired,
            kind="terminal" if key.is_terminal_key else "standard",
        )

    @staticmethod
    def to_created_result(key: ApiKey, raw_key: str) -> CreatedApiKeyResult:
        return CreatedApiKeyResult(
            id=key.id,
            public_id=key.public_id,
            name=key.name,
            token_prefix=key.token_prefix,
            permissions=key.permissions,
            created_by_id=key.created_by_id,
            created=key.created,
            expires_at=key.expires_at,
            revoked_at=key.revoked_at,
            is_expired=key.is_expired,
            kind="terminal" if key.is_terminal_key else "standard",
            key=raw_key,
        )

    @staticmethod
    def usage_to_result(entry: ApiKeyUsageLogEntry) -> ApiKeyUsageLogEntryResult:
        return ApiKeyUsageLogEntryResult(
            id=entry.id,
            public_id=entry.public_id,
            key_id=entry.key_id,
            called_at=entry.called_at,
            method=entry.method,
            path=entry.path,
            status_code=entry.status_code,
        )
