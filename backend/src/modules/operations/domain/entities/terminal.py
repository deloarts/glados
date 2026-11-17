"""
A terminal: one physical wall display, identified by the Ed25519 public key
of the glados-terminal bridge it runs on. The private key never leaves the
bridge; Glados only stores the public key and checks signatures against it.

An unknown device registers itself as pending with a pairing code shown on
its screen, someone types that code to approve it, and from then on it shows
the infoscreen assigned to it. Revoking cuts it off at once, because every
device request reloads this row. `reload_requested_at` and
`identify_requested_at` are commands to the device that travel through the
live row sync like any other change, and so does a display override,
which forces the display on or off until a given moment.

The device reports its hardware details with every session. They are kept
as one value object; the serials and the hostname in it, like the client
addresses and the key fingerprint, identify the device and are only shown
to holders of manage:terminals.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.operations.domain.value_objects.display_schedule import DisplayPower
from src.modules.operations.domain.value_objects.display_schedule import DisplaySchedule
from src.modules.operations.domain.value_objects.display_schedule import DisplayScheduleMode
from src.modules.operations.domain.value_objects.terminal import TerminalMode
from src.modules.operations.domain.value_objects.terminal import TerminalStatus
from src.modules.operations.domain.value_objects.terminal_device_details import (
    TerminalDeviceDetails,
)
from src.modules.platform.domain.entities.user import User
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class Terminal(Entity):
    # ── Identity ──────────────────────────────────────────────────────
    public_key: str  # raw 32-byte Ed25519 key, base64url without padding
    public_key_fingerprint: str  # first 16 hex characters of SHA-256 over the raw key

    # ── State ─────────────────────────────────────────────────────────
    status: TerminalStatus
    mode: TerminalMode
    name: str | None
    pairing_code: str | None  # set while pending
    pairing_expires_at: datetime | None
    infoscreen_id: int | None
    api_key_id: int | None  # the terminal key the device registered with

    # ── Telemetry, as the device reported it ──────────────────────────
    first_seen_at: datetime
    last_seen_at: datetime
    last_ip: str | None = None
    user_agent: str | None = None
    screen_width: int | None = None
    screen_height: int | None = None
    frontend_version: str | None = None
    bridge_version: str | None = None
    device: TerminalDeviceDetails | None = None
    device_reported_at: datetime | None = None

    # ── Placement ─────────────────────────────────────────────────────
    # Where the display hangs, free text such as "Hall 2, north wall".
    location: str | None = None

    # ── Approval and commands ─────────────────────────────────────────
    approved_at: datetime | None = None
    approved_by_id: int | None = None
    revoked_at: datetime | None = None
    reload_requested_at: datetime | None = None
    identify_requested_at: datetime | None = None
    # Forces the display on or off until display_override_until.
    display_override: DisplayPower | None = None
    display_override_until: datetime | None = None

    # ── Clone detection ───────────────────────────────────────────────
    # When the latest access token was issued and to which address. A new
    # session from another address while that token is still valid marks
    # the terminal as possibly cloned.
    last_session_at: datetime | None = None
    last_session_ip: str | None = None
    duplicate_detected_at: datetime | None = None

    # ── Server-managed ────────────────────────────────────────────────
    created: datetime | None = None
    changed: datetime | None = None

    # ── Denormalized (read-only, populated by repository mapper) ──────
    infoscreen_name: str | None = None
    api_key_name: str | None = None
    approved_by: User | None = None
    # The display schedule of the shown screen and which schedule it follows.
    screen_display_schedule: DisplaySchedule | None = None
    screen_off_on_holidays: bool = False
    screen_display_schedule_mode: DisplayScheduleMode = DisplayScheduleMode.OWN
