"""
Validates an API key (opaque, hashed) and returns its backing
service-account User. Read-only, no writes on the hot auth path;
"last used" is derived from the usage log rather than a denormalized
column here.
"""

from collections.abc import Callable

from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InactiveUserError
from src.modules.platform.domain.exceptions import InvalidTokenError
from src.modules.platform.domain.exceptions import UserNotFoundError
from src.modules.platform.ports.outbound.repositories.api_key_repository import IApiKeyRepository
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository


class ValidateApiKey:
    def __init__(
        self,
        key_repo: IApiKeyRepository,
        user_repo: IUserRepository,
        hash_fn: Callable[[str], str],
    ) -> None:
        self._keys = key_repo
        self._users = user_repo
        self._hash = hash_fn

    async def execute(self, raw_key: str) -> tuple[User, int]:
        """Returns (user, key_id) so callers can record which key was used."""
        if not raw_key:
            raise InvalidTokenError("No API key provided")

        key = await self._keys.get_by_token_hash(self._hash(raw_key))
        if key is None:
            raise InvalidTokenError("Invalid API key")

        if key.is_revoked:
            raise InvalidTokenError("API key has been revoked")

        if key.is_expired:
            raise InvalidTokenError("API key has expired")

        user = found_or_raise(
            await self._users.get_by_id(key.user_id),
            UserNotFoundError,
            f"Service user #{key.user_id} not found",
        )

        if not user.is_active:
            raise InactiveUserError(f"Service user {user.username!r} is inactive")

        return user, key.id
