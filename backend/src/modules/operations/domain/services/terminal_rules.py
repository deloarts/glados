"""
Business rules for terminals: who may manage them, the pairing code and its
lifetime, approval, revocation, the return of a revoked device to pending,
the pending cap, the location text, the access policy of the security
settings, and clone detection. No I/O.
"""

import hmac
import secrets
from collections.abc import Collection
from datetime import datetime

from src.modules.operations.domain.entities.terminal import Terminal
from src.modules.operations.domain.errors import InvalidTerminalLocationError
from src.modules.operations.domain.errors import PairingCodeExpiredError
from src.modules.operations.domain.errors import PairingCodeMismatchError
from src.modules.operations.domain.errors import PendingTerminalLimitError
from src.modules.operations.domain.errors import TerminalIpNotAllowedError
from src.modules.operations.domain.errors import TerminalModeNotSupportedError
from src.modules.operations.domain.errors import TerminalNotPendingError
from src.modules.operations.domain.errors import TerminalsDisabledError
from src.modules.operations.domain.value_objects.terminal import MAX_LOCATION_LENGTH
from src.modules.operations.domain.value_objects.terminal import MAX_PENDING_TERMINALS
from src.modules.operations.domain.value_objects.terminal import PAIRING_CODE_ALPHABET
from src.modules.operations.domain.value_objects.terminal import PAIRING_CODE_LENGTH
from src.modules.operations.domain.value_objects.terminal import PAIRING_CODE_TTL
from src.modules.operations.domain.value_objects.terminal import SUPPORTED_TERMINAL_MODES
from src.modules.operations.domain.value_objects.terminal import TERMINAL_TOKEN_TTL
from src.modules.operations.domain.value_objects.terminal import TerminalMode
from src.modules.operations.domain.value_objects.terminal import TerminalStatus
from src.modules.platform.domain.entities.admin_settings.maintenance import AdminMaintenanceSettings
from src.modules.platform.domain.entities.admin_settings.security import AdminSecuritySettings
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import MaintenanceModeError
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.services.maintenance_policy import DEFAULT_MESSAGE
from src.modules.platform.domain.services.maintenance_policy import ip_is_allowed
from src.modules.platform.domain.value_objects.permission import Permission

# Draws before giving up on a free code. With 31^6 codes and at most a few
# dozen pending terminals a collision is already rare on the first draw.
_MAX_CODE_DRAWS = 100


def assert_can_manage(actor: User) -> None:
    assert_has_permission(actor, Permission.MANAGE_TERMINALS, "manage", "terminals")


def may_see_identifying_details(actor: User) -> bool:
    """Whether the reader may see what identifies one device: the key
    fingerprint, the client addresses, the serials and the hostname."""
    return actor.has_permission(Permission.MANAGE_TERMINALS)


def assert_mode_supported(mode: str) -> None:
    if mode not in SUPPORTED_TERMINAL_MODES:
        raise TerminalModeNotSupportedError(f"Terminal mode {mode!r} is not available yet.")


def normalise_location(location: str | None) -> str | None:
    """The location as stored: trimmed, None when empty."""
    if location is None:
        return None
    location = location.strip()
    if len(location) > MAX_LOCATION_LENGTH:
        raise InvalidTerminalLocationError(
            f"location must be at most {MAX_LOCATION_LENGTH} characters."
        )
    return location or None


def new_pairing_code(taken: Collection[str]) -> str:
    """A random code from the unambiguous alphabet that no pending terminal
    holds."""
    for _ in range(_MAX_CODE_DRAWS):
        code = "".join(secrets.choice(PAIRING_CODE_ALPHABET) for _ in range(PAIRING_CODE_LENGTH))
        if code not in taken:
            return code
    raise PendingTerminalLimitError("Could not find a free pairing code; try again shortly.")


def normalise_pairing_code(code: str) -> str:
    """The code as stored, so a code typed in lower case or with spaces
    still matches."""
    return "".join(code.split()).upper()


def pairing_code_expired(terminal: Terminal, now: datetime) -> bool:
    return terminal.pairing_expires_at is None or terminal.pairing_expires_at <= now


def issue_pairing_code(terminal: Terminal, taken: Collection[str], now: datetime) -> None:
    """Gives the terminal a fresh code valid for the pairing lifetime."""
    terminal.pairing_code = new_pairing_code(taken)
    terminal.pairing_expires_at = now + PAIRING_CODE_TTL


def assert_pending_capacity(active_pending: int) -> None:
    """Refuses another pending terminal once the cap is reached."""
    if active_pending >= MAX_PENDING_TERMINALS:
        raise PendingTerminalLimitError(
            f"{MAX_PENDING_TERMINALS} terminals already wait for approval; approve or "
            "delete some first."
        )


def approve(
    terminal: Terminal,
    *,
    pairing_code: str,
    name: str,
    mode: TerminalMode,
    infoscreen_id: int | None,
    actor: User,
    now: datetime,
    location: str | None = None,
) -> None:
    """Approves a pending terminal whose code matches and has not expired.
    The comparison runs in constant time."""
    if terminal.status != TerminalStatus.PENDING.value:
        raise TerminalNotPendingError(f"Terminal #{terminal.id} is not waiting for approval.")
    assert_mode_supported(mode)
    if pairing_code_expired(terminal, now):
        raise PairingCodeExpiredError(
            "The pairing code has expired. The display shows a new one within a few minutes."
        )
    typed = normalise_pairing_code(pairing_code)
    if not hmac.compare_digest(typed.encode(), (terminal.pairing_code or "").encode()):
        raise PairingCodeMismatchError("The pairing code does not match the one on the display.")
    terminal.status = TerminalStatus.APPROVED
    terminal.name = name
    terminal.location = normalise_location(location)
    terminal.mode = mode
    terminal.infoscreen_id = infoscreen_id
    terminal.pairing_code = None
    terminal.pairing_expires_at = None
    terminal.approved_at = now
    terminal.approved_by_id = actor.id
    terminal.revoked_at = None
    terminal.duplicate_detected_at = None


def revoke(terminal: Terminal, now: datetime) -> None:
    """Cuts the terminal off. Its screen stays assigned, so a later approval
    can keep it."""
    terminal.status = TerminalStatus.REVOKED
    terminal.revoked_at = now
    terminal.pairing_code = None
    terminal.pairing_expires_at = None


def return_to_pending(terminal: Terminal, taken: Collection[str], now: datetime) -> None:
    """A revoked device that signs in again waits for a new approval."""
    terminal.status = TerminalStatus.PENDING
    terminal.approved_at = None
    terminal.approved_by_id = None
    issue_pairing_code(terminal, taken, now)


def assert_access_allowed(settings: AdminSecuritySettings, client_ip: str | None) -> None:
    """Terminal sign-in and every device request need terminals switched on
    and, when an allowlist is set, a client address on it."""
    if not settings.enable_terminals:
        raise TerminalsDisabledError("Terminals are switched off in the security settings.")
    if settings.terminal_allowed_ips and not ip_is_allowed(
        client_ip, settings.terminal_allowed_ips
    ):
        raise TerminalIpNotAllowedError(
            f"Terminals may not connect from {client_ip or 'an unknown address'}."
        )


def assert_maintenance_allows_device(
    settings: AdminMaintenanceSettings, client_ip: str | None
) -> None:
    """Maintenance mode holds devices back too, unless their address is on
    the maintenance allowlist."""
    if not settings.enabled or ip_is_allowed(client_ip, settings.allowed_ips):
        return
    raise MaintenanceModeError(settings.message or DEFAULT_MESSAGE)


def detect_clone(terminal: Terminal, client_ip: str | None, now: datetime) -> bool:
    """Whether a session for `client_ip` arrives while the token issued to
    another address is still valid, which suggests a copied key. Marks the
    terminal when it does; nothing is revoked automatically."""
    previous = terminal.last_session_at
    clone = (
        previous is not None
        and previous + TERMINAL_TOKEN_TTL > now
        and terminal.last_session_ip is not None
        and terminal.last_session_ip != client_ip
    )
    if clone:
        terminal.duplicate_detected_at = now
    terminal.last_session_at = now
    terminal.last_session_ip = client_ip
    return clone
