"""
Issuing and redeeming the challenge of a passkey ceremony. The challenge
travels in a short-lived signed token from the options request to the
verify request, so nothing is stored in between, and redeeming claims it
once in the replay guard, so a captured browser response cannot be sent a
second time while the token is still valid.
"""

from src.modules.platform.domain.value_objects import token_scope
from src.modules.platform.infrastructure.security.token import PASSKEY_CHALLENGE_MINUTES
from src.modules.platform.infrastructure.security.token import create_passkey_challenge_token
from src.modules.platform.infrastructure.security.token import get_token_payload
from src.modules.platform.ports.outbound.replay_guard_port import IReplayGuard

_CHALLENGE_TTL_SECONDS = PASSKEY_CHALLENGE_MINUTES * 60


def issue_passkey_challenge(challenge: str, scope: str, user_id: int | None = None) -> str:
    """The token for `challenge`. A registration challenge names its user,
    so it cannot be redeemed under another account's session."""
    return create_passkey_challenge_token(challenge, scope, subject=user_id)


async def redeem_passkey_challenge(
    token: str, *, scope: str, replay_guard: IReplayGuard, user_id: int | None = None
) -> str | None:
    """The challenge inside `token`, or None when the token is invalid,
    expired, of another flow or another user, or was already redeemed."""
    payload = get_token_payload(token, persistent=False)
    if payload is None or payload.scope != scope or not payload.chl:
        return None
    if scope == token_scope.PASSKEY_REGISTRATION and payload.sub != str(user_id):
        return None
    claimed = await replay_guard.consume_once(
        f"glados:passkey:challenge:{payload.chl}", ttl_seconds=_CHALLENGE_TTL_SECONDS
    )
    return payload.chl if claimed else None
