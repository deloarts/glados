"""
Validates a personal access token (opaque, hashed) and returns the
authenticated User, impersonating the human who created it, but with
permissions capped to whatever that specific token was scoped to at
creation. Read-only, no writes on the hot auth path; usage is derived
from the usage log rather than a denormalized column here.
"""

from collections.abc import Callable
from dataclasses import replace

from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InactiveUserError
from src.modules.platform.domain.exceptions import InvalidTokenError
from src.modules.platform.domain.exceptions import UserNotFoundError
from src.modules.platform.ports.outbound.repositories.pat_repository import IPatRepository
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository


class ValidatePat:
    def __init__(
        self,
        pat_repo: IPatRepository,
        user_repo: IUserRepository,
        hash_fn: Callable[[str], str],
    ) -> None:
        self._pats = pat_repo
        self._users = user_repo
        self._hash = hash_fn

    async def execute(self, raw_token: str) -> tuple[User, int]:
        """Returns (user, pat_id) so callers can record which token was used."""
        if not raw_token:
            raise InvalidTokenError("No personal access token provided")

        token = await self._pats.get_by_token_hash(self._hash(raw_token))
        if token is None:
            raise InvalidTokenError("Invalid personal access token")

        if token.is_revoked:
            raise InvalidTokenError("Personal access token has been revoked")

        if token.is_expired:
            raise InvalidTokenError("Personal access token has expired")

        user = found_or_raise(
            await self._users.get_by_id(token.user_id),
            UserNotFoundError,
            f"User #{token.user_id} not found",
        )

        # PatRules.assert_can_create already refuses to mint one for the
        # system account; this check rejects any such token that exists
        # anyway, which would otherwise validate forever. Checked before
        # is_active so it wins over a merely-inactive-account reason too.
        if user.is_systemuser:
            raise InvalidTokenError("Personal access tokens are not valid for the system account")

        if not user.is_active:
            raise InactiveUserError(f"User {user.username!r} is inactive")

        # Cap the effective principal at the token's own scope, and that
        # scope at what the owner holds today: a token keeps no permission
        # its owner has lost since it was created, directly or by leaving a
        # group. The group permissions are folded into that intersection and
        # cleared, so nothing reaches past it. is_systemuser is forced off
        # here too as a second guard, the raise above already refuses every
        # system-user-owned token, so in practice `user` is never a system
        # user here, but the shortcut in User.has_permission must never be
        # reachable through a scoped-down token regardless.
        held = set(user.effective_permissions)
        scoped_user = replace(
            user,
            permissions=[p for p in token.permissions if p in held],
            group_permissions=[],
            is_systemuser=False,
        )
        return scoped_user, token.id
