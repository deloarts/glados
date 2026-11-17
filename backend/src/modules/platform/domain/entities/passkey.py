"""
A WebAuthn credential (passkey) a user registered on one authenticator,
such as Windows Hello on a laptop, Touch ID or a security key. Only the
public key is stored, the private key never leaves the authenticator, so a
database leak yields nothing that can sign a login.

A passkey replaces both the password and the TOTP code: the authenticator
proves possession of the device and verifies the user (PIN or biometric)
itself. That is why only a verified registration may create one.
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime

from src.shared_kernel.domain.entities.base import Entity
from src.shared_kernel.domain.services.clock import now_utc

# Long enough for "Office PC (Windows Hello)" style names, short enough to
# fit a table cell.
PASSKEY_NAME_MAX_LENGTH = 100


@dataclass
class Passkey(Entity):
    user_id: int
    credential_id: bytes  # the authenticator's credential ID, unique per authenticator
    public_key: bytes  # COSE-encoded public key from the registration response
    sign_count: int  # the authenticator's signature counter, 0 when it keeps none
    name: str
    created_at: datetime  # UTC, timezone-aware
    last_used_at: datetime | None = None  # UTC, aware; the last login it signed
    # Transport hints the browser reported ("internal", "usb", "hybrid"...),
    # handed back on login so the browser knows where to look.
    transports: list[str] = field(default_factory=list)
    # Whether the credential is synced to other devices (a cloud passkey)
    # rather than bound to this one authenticator.
    backed_up: bool = False


def passkey_name(name: str) -> str:
    """The name as stored: trimmed and cut to PASSKEY_NAME_MAX_LENGTH."""
    return name.strip()[:PASSKEY_NAME_MAX_LENGTH]


def make_passkey(
    *,
    user_id: int,
    credential_id: bytes,
    public_key: bytes,
    sign_count: int,
    name: str,
    transports: list[str],
    backed_up: bool,
) -> Passkey:
    """A fresh, unpersisted passkey (id=0) registered now."""
    return Passkey(
        id=0,
        user_id=user_id,
        credential_id=credential_id,
        public_key=public_key,
        sign_count=sign_count,
        name=passkey_name(name),
        created_at=now_utc(),
        transports=list(transports),
        backed_up=backed_up,
    )
