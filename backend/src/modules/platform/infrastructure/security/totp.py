"""
TOTP (Time-based One-Time Password) utilities for 2FA.
Wraps pyotp, no business logic here.
"""

import time
from collections.abc import Awaitable
from collections.abc import Callable

import pyotp

# pyotp.TOTP's default step length, matches verify_totp below, which
# never overrides `interval`. Kept as a constant here (rather than
# re-deriving it from a TOTP instance) so verify_totp_once needs no
# secret-bearing object of its own beyond the one verify_totp already
# builds internally.
_TOTP_STEP_SECONDS = 30

# TTL for the IReplayGuard key a caller's `consume` closes over: three steps,
# enough for one verification without a stale claim outliving the code's
# validity. Every call site uses this rather than its own number.
TOTP_REPLAY_TTL_SECONDS = 90


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def verify_totp(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code)


async def verify_totp_once(
    secret: str, code: str, *, consume: Callable[[str], Awaitable[bool]]
) -> bool:
    """verify_totp, plus one-shot replay protection: a code that verifies
    correctly is accepted only the first time it is presented within its
    current 30-second step. `consume(counter)` claims that step (e.g.
    RedisReplayGuard.consume_once behind a `SET NX EX` on a key scoped to
    this step) and returns whether this call is the one that claimed it,
    False on a second presentation of the same code, whether that is an
    attacker replaying an intercepted code or the legitimate user's own
    double-submit (a slow retry, a double click). Collapsing both into the
    same "invalid code" outcome, never a distinct "already used" error,
    is deliberate: telling a replaying attacker their code WAS valid is
    exactly the confirmation they should never get.
    """
    if not verify_totp(secret, code):
        return False
    counter = str(int(time.time()) // _TOTP_STEP_SECONDS)
    return await consume(counter)


def get_totp_provisioning_uri(secret: str, username: str, issuer: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=issuer)
