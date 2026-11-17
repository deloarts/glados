"""
JWT creation and decoding. Reads keys from Settings, no file I/O at import time.
"""

from datetime import timedelta
from typing import Any

import jwt
from pydantic import BaseModel
from pydantic import ValidationError

from src.modules.platform.domain.value_objects import token_scope
from src.modules.platform.infrastructure.config.settings import cfg
from src.shared_kernel.domain.services.clock import now_utc


class TokenPayload(BaseModel):
    # create_access_token/create_partial_token/create_setup_token always
    # write str(subject), never a bare int or bool, so only a token forged
    # by hand could carry anything wider than str.
    sub: str | None = None
    ver: int | None = None
    scope: str | None = None
    # Session row public_id. Present on session tokens; absent on
    # partial/setup tokens, which have no server-side row.
    sid: str | None = None
    # Base64url WebAuthn challenge. Present on passkey challenge tokens only.
    chl: str | None = None


def _secret_key(persistent: bool) -> str:
    if cfg.debug or persistent:
        return cfg.security.secret_key_persistent
    return cfg.security.secret_key_non_persistent


def create_access_token(
    subject: Any,
    persistent: bool,
    expires_delta: timedelta | None,
    token_version: int | None = None,
    sid: str | None = None,
) -> str:
    """Sign an access token.

    `expires_delta` is deliberately required, with `None` meaning "no exp
    claim": session tokens are bounded by their server-side row (idle
    timeout + revocation, see domain/services/session_rules.py), not by
    JWT expiry, so a silent time-based default here would only mask a
    caller that forgot to decide.
    """
    payload: dict[str, Any] = {"sub": str(subject)}
    if expires_delta is not None:
        payload["exp"] = now_utc() + expires_delta
    if token_version is not None:
        payload["ver"] = token_version
    if sid is not None:
        payload["sid"] = sid
    token: str = jwt.encode(payload, _secret_key(persistent), algorithm=cfg.security.algorithm)
    return token


def create_partial_token(subject: Any) -> str:
    """Short-lived (5 min) TOTP-challenge token. Cannot access protected routes."""
    expire = now_utc() + timedelta(minutes=5)
    payload: dict[str, Any] = {
        "exp": expire,
        "sub": str(subject),
        "scope": token_scope.TOTP_PENDING,
    }
    token: str = jwt.encode(
        payload, _secret_key(persistent=False), algorithm=cfg.security.algorithm
    )
    return token


def get_token_payload(token: str, persistent: bool) -> TokenPayload | None:
    """Decodes a token and returns its payload, or None if invalid."""
    if not token:
        return None
    try:
        raw = jwt.decode(token, _secret_key(persistent), algorithms=[cfg.security.algorithm])
        return TokenPayload(**raw)
    except (jwt.PyJWTError, ValidationError):
        return None


def get_subject_from_token(token: str, persistent: bool) -> str | None:
    """Returns the subject string from a valid token, or None."""
    payload = get_token_payload(token, persistent)
    if payload is None or payload.sub is None:
        return None
    return str(payload.sub)


# Enrolment is slower than typing a code you already have: install an
# authenticator, scan a QR, then type. Five minutes (the TOTP_PENDING
# window) is not enough for a first-timer, so this gets its own.
SETUP_TOKEN_MINUTES = 15


def create_setup_token(subject: Any, token_version: int | None = None) -> str:
    """Short-lived token for a user who must enrol in 2FA before they can
    do anything else. Accepted only by the enrolment endpoints.

    `token_version` must be supplied: this token is validated by
    ValidateWebToken, which compares it against the user's current version
    and rejects a mismatch as "Session invalidated". Omitting it means the
    claim defaults to 0, so every user who has ever been force-logged-out
    (version > 0) is refused at enrolment.
    """
    expire = now_utc() + timedelta(minutes=SETUP_TOKEN_MINUTES)
    payload: dict[str, Any] = {
        "exp": expire,
        "sub": str(subject),
        "scope": token_scope.TOTP_SETUP,
    }
    if token_version is not None:
        payload["ver"] = token_version
    token: str = jwt.encode(
        payload, _secret_key(persistent=False), algorithm=cfg.security.algorithm
    )
    return token


# Matches the time a browser gives the user to answer the passkey prompt,
# with room for a slow PIN entry.
PASSKEY_CHALLENGE_MINUTES = 5


def create_passkey_challenge_token(challenge: str, scope: str, subject: Any | None = None) -> str:
    """Short-lived token carrying a WebAuthn challenge (base64url) between
    the options and the verify request, so no server-side state is kept
    in between. `scope` names the flow it belongs to; a registration token
    also carries its user as `sub`. The verifying use case claims the
    challenge once, so a token cannot be redeemed twice."""
    payload: dict[str, Any] = {
        "exp": now_utc() + timedelta(minutes=PASSKEY_CHALLENGE_MINUTES),
        "scope": scope,
        "chl": challenge,
    }
    if subject is not None:
        payload["sub"] = str(subject)
    token: str = jwt.encode(
        payload, _secret_key(persistent=False), algorithm=cfg.security.algorithm
    )
    return token
