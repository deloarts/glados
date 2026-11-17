"""
Password hashing. Thin wrapper around bcrypt.

bcrypt is deliberately slow CPU work (about 100 ms per hash), so async code
uses `averify_hash` / `aget_hash`, which run it in a worker thread instead
of stalling the event loop for every other request.

bcrypt only ever reads the first 72 bytes of its input. bcrypt 4 dropped the
rest silently, and bcrypt 5 raises ValueError instead, so this module cuts
the UTF-8 bytes at 72 itself. That keeps every stored hash verifiable and
keeps the user-facing rule unchanged: a password that logged in before still
logs in, and characters past the 72nd byte still do not count.
"""

import secrets

from anyio import to_thread
from bcrypt import checkpw
from bcrypt import gensalt
from bcrypt import hashpw

# Marks a stored hash that no password can ever match. Directory-backed
# accounts get one instead of a real digest, so there is no local credential
# to guess and no copy of anyone's directory password in our database.
#
# `!` is the sentinel because bcrypt digests always start with `$2`, so the
# prefix cannot collide with a real hash. Django uses the same marker for
# set_unusable_password(), and django-auth-ldap writes it for every
# directory-backed user; the convention is worth borrowing rather than
# inventing.
UNUSABLE_PASSWORD_PREFIX = "!"


def unusable_password_hash() -> str:
    """Return a hash value that no password can match.

    The random tail is not a secret and is never verified against; it exists
    so two directory users never share a stored value, which would otherwise
    make "same hash" readable as "same password" to anyone reading the table.
    """
    return UNUSABLE_PASSWORD_PREFIX + secrets.token_urlsafe(32)


def is_unusable_hash(hashed: str | None) -> bool:
    """Whether this stored hash marks an account with no local password."""
    return not hashed or hashed.startswith(UNUSABLE_PASSWORD_PREFIX)


# The most input bcrypt reads; anything after it never affected a hash.
BCRYPT_MAX_INPUT_BYTES = 72


def _bcrypt_input(value: str) -> bytes:
    """The UTF-8 bytes bcrypt actually hashes. The cut may split a multi-byte
    character, which is what bcrypt 4 did as well, so it has to happen on
    bytes rather than characters."""
    return value.encode("utf-8")[:BCRYPT_MAX_INPUT_BYTES]


def verify_hash(plain: str, hashed: str) -> bool:
    """Returns True if plain matches hashed."""
    return checkpw(
        password=_bcrypt_input(plain),
        hashed_password=hashed.encode("utf-8"),
    )


def get_hash(value: str) -> str:
    """Returns a bcrypt hash of value."""
    salt = gensalt()
    return hashpw(_bcrypt_input(value), salt).decode("utf-8")


async def averify_hash(plain: str, hashed: str) -> bool:
    """verify_hash, off the event loop."""
    return await to_thread.run_sync(verify_hash, plain, hashed)


async def aget_hash(value: str) -> str:
    """get_hash, off the event loop."""
    return await to_thread.run_sync(get_hash, value)
