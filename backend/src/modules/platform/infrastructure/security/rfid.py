"""
Deterministic HMAC-SHA256 of an RFID tag, the credential of record for a
user's tag and the key SqlAlchemyUserRepository.get_by_rfid looks it up
by in O(1). The value has to be deterministic to be searchable, which a
salted hash such as bcrypt is not. Unlike an API key
(src/modules/platform/infrastructure/security/api_key.py) an RFID UID is
low-entropy, often a handful of printable bytes from a cheap chip, so a
*plain* SHA-256 would be offline-brute-forceable from a leaked DB dump:
an attacker just precomputes SHA-256 over every plausible UID and matches
against the stored values. Keying the hash with
cfg.security.secret_key_persistent as a pepper closes that, without the
app secret the value is not invertible even for a low-entropy input.

The tag is not a secret, it identifies and does not authenticate (see
identify_operator_by_rfid.py), so no slow hash is needed on top.
"""

import hashlib
import hmac

from src.modules.platform.infrastructure.config.settings import cfg


def rfid_lookup(tag: str) -> str:
    return hmac.new(
        cfg.security.secret_key_persistent.encode("utf-8"),
        tag.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
