"""Vocabulary and fixed limits of terminals, the wall displays that sign in
with a device key pair and show an infoscreen.

A terminal is pending until someone approves it by typing the pairing code
its screen shows, approved afterwards, and revoked when it was cut off. The
`kiosk` mode is reserved for a later interactive mode; the domain rules
refuse it for now.
"""

from datetime import timedelta
from enum import unique
from typing import Final

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class TerminalStatus(StrValueEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REVOKED = "revoked"


@unique
class TerminalMode(StrValueEnum):
    INFOSCREEN = "infoscreen"
    KIOSK = "kiosk"

    @classmethod
    def default(cls) -> "TerminalMode":
        return cls.INFOSCREEN


# Modes the rules accept today.
SUPPORTED_TERMINAL_MODES: Final = frozenset({TerminalMode.INFOSCREEN.value})

# Pairing codes leave out 0, O, 1, I and L, which read alike on a TV
# across a room.
PAIRING_CODE_ALPHABET: Final = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
PAIRING_CODE_LENGTH: Final = 6
PAIRING_CODE_TTL: Final = timedelta(hours=1)

# Registration by an unknown device stops once this many terminals wait
# for approval, so a leaked terminal key cannot flood the list.
MAX_PENDING_TERMINALS: Final = 20

# Longest location text, such as "Hall 2, north wall above gate 3".
MAX_LOCATION_LENGTH: Final = 200

# Lifetime of a terminal access token. The device signs a fresh challenge
# before it runs out.
TERMINAL_TOKEN_TTL: Final = timedelta(minutes=15)

# Lifetime of a challenge nonce.
TERMINAL_CHALLENGE_TTL_SECONDS: Final = 60

# How stale the stored last-seen time may get before a device request
# writes it again, so a polling device does not write on every request.
TERMINAL_LAST_SEEN_TOUCH: Final = timedelta(minutes=2)

# A pending terminal whose code expired this long ago is removed the next
# time an unknown device registers.
STALE_PENDING_AFTER: Final = timedelta(days=1)
