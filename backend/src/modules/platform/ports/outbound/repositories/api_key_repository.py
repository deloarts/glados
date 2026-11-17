"""
Abstract interface for API key persistence.
The application layer depends on this, never on the SQLAlchemy implementation.
"""

from dataclasses import dataclass
from datetime import date
from typing import Protocol
from typing import runtime_checkable

from src.modules.platform.domain.entities.api_key import ApiKey


@dataclass
class ApiKeyFilterDto:
    skip: int | None = None
    limit: int | None = None
    include_revoked: bool = False
    search: str | None = None
    order_by: str | None = None
    order_dir: str | None = None
    token_prefix: str | None = None  # substring of the visible token prefix
    created_from: date | None = None  # inclusive calendar day
    created_to: date | None = None  # inclusive calendar day
    # "never" has no expiry, "expired" is past it, "active" expires later,
    # "unexpired" is either "never" or "active".
    expiry: str | None = None
    # "terminal" keeps the keys holding connect:terminals, "standard" the rest.
    kind: str | None = None


@runtime_checkable
class IApiKeyRepository(Protocol):
    async def get_by_id(self, id: int) -> ApiKey | None: ...

    async def get_by_token_hash(self, token_hash: str) -> ApiKey | None: ...

    async def get_multi(self, filters: ApiKeyFilterDto) -> tuple[int, list[ApiKey]]: ...

    async def save(self, key: ApiKey) -> ApiKey:
        """Insert (id == 0) or update (id > 0) without committing. Keys are
        otherwise immutable, the only legitimate update is stamping
        revoked_at."""
        ...
