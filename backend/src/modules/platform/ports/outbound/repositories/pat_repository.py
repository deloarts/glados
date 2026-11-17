"""
Abstract interface for personal access token persistence.
The application layer depends on this, never on the SQLAlchemy implementation.
"""

from dataclasses import dataclass
from datetime import date
from typing import Protocol
from typing import runtime_checkable

from src.modules.platform.domain.entities.personal_access_token import PersonalAccessToken


@dataclass
class PatFilterDto:
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


@runtime_checkable
class IPatRepository(Protocol):
    async def get_by_id(self, id: int) -> PersonalAccessToken | None: ...

    async def get_by_token_hash(self, token_hash: str) -> PersonalAccessToken | None: ...

    async def get_multi_for_user(
        self, user_id: int, filters: PatFilterDto
    ) -> tuple[int, list[PersonalAccessToken]]: ...

    async def save(self, token: PersonalAccessToken) -> PersonalAccessToken:
        """Insert (id == 0) or update (id > 0) without committing. Tokens are
        otherwise immutable, the only legitimate update is stamping
        revoked_at."""
        ...

    async def list_unrevoked_unexpired(
        self, user_id: int | None = None
    ) -> list[PersonalAccessToken]:
        """Every token that still authenticates, or only those of `user_id`,
        for revoking agent tokens when they go idle or their owner withdraws
        the agent consent."""
        ...

    async def revoke_all_for_user(self, user_id: int) -> int:
        """Stamps revoked_at on every currently-active token owned by user_id.
        Returns the number of tokens revoked. Used by force-logout to
        invalidate all of a user's PATs at once, and by the self-service
        'revoke all' action. Does not commit."""
        ...
