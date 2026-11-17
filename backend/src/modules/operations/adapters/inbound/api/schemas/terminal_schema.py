"""
HTTP schemas for terminals: the device sign-in and state under
`/terminal-device`, the admin list and actions under `/terminals`, the
messages to terminals under `/terminal-broadcasts`, and the terminal key
request under `/admin/api-keys/terminal`.

The device details a session carries are untrusted. The wire only refuses
what is absurd (text over a kilobyte, a number that is not a finite
number); the domain parser cuts every text to its own cap and drops
implausible numbers, so an odd report never keeps a display from signing in.
"""

from datetime import datetime
from typing import Any
from typing import Literal

from pydantic import AwareDatetime
from pydantic import BaseModel
from pydantic import Field

from src.modules.operations.application.dto.terminal_dto import BroadcastSeverityValue
from src.modules.operations.application.dto.terminal_dto import BroadcastStyleValue
from src.modules.operations.application.dto.terminal_dto import TerminalBroadcastMessage
from src.modules.operations.domain.value_objects.terminal import MAX_LOCATION_LENGTH
from src.modules.operations.domain.value_objects.terminal_broadcast import MAX_BROADCAST_TARGETS
from src.modules.operations.domain.value_objects.terminal_broadcast import MAX_BROADCAST_TEXT_LENGTH
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.platform.adapters.inbound.api.schemas.user_schema import PublicUserResponse

TerminalStatusField = Literal["pending", "approved", "revoked"]
TerminalModeField = Literal["infoscreen", "kiosk"]
DisplayPowerField = Literal["on", "off"]

_KEY_MAX = 128
_SIGNATURE_MAX = 256
_NONCE_MAX = 256
_TEXT_MAX = 512
_VERSION_MAX = 64
_SCREEN_MAX = 100_000
_DETAIL_TEXT_MAX = 1024
_TARGETS_MAX = MAX_BROADCAST_TARGETS


def _detail_text() -> Any:
    return Field(default=None, max_length=_DETAIL_TEXT_MAX)


def _detail_number() -> Any:
    return Field(default=None, allow_inf_nan=False)


# ── Device ────────────────────────────────────────────────────────────


class TerminalChallengeRequest(BaseModel):
    # Raw 32-byte Ed25519 public key, base64url without padding.
    public_key: str = Field(..., min_length=1, max_length=_KEY_MAX)


class TerminalChallengeResponse(ResponseModel):
    nonce: str
    expires_at: datetime


class TerminalDeviceDetailsRequest(BaseModel):
    """The hardware details the bridge reports. Every field is optional; the
    page sends what the bridge knows."""

    computer_model: str | None = _detail_text()
    computer_serial: str | None = _detail_text()
    ram_mb: int | None = None
    cpu_temperature_c: float | None = _detail_number()
    uptime_seconds: int | None = None
    kernel: str | None = _detail_text()
    os_name: str | None = _detail_text()
    hostname: str | None = _detail_text()
    under_voltage: bool | None = None
    throttled: bool | None = None
    display_make: str | None = _detail_text()
    display_model: str | None = _detail_text()
    display_serial: str | None = _detail_text()
    display_width_px: int | None = None
    display_height_px: int | None = None
    display_width_mm: int | None = None
    display_height_mm: int | None = None
    display_connector: str | None = _detail_text()
    display_connected: bool | None = None
    display_power_state: str | None = _detail_text()
    cec_available: bool | None = None


class TerminalSessionRequest(BaseModel):
    public_key: str = Field(..., min_length=1, max_length=_KEY_MAX)
    nonce: str = Field(..., min_length=1, max_length=_NONCE_MAX)
    # Ed25519 signature over b"glados-terminal-auth-v1:" + nonce, base64url
    # without padding.
    signature: str = Field(..., min_length=1, max_length=_SIGNATURE_MAX)
    user_agent: str | None = Field(default=None, max_length=_TEXT_MAX)
    screen_width: int | None = Field(default=None, ge=0, le=_SCREEN_MAX)
    screen_height: int | None = Field(default=None, ge=0, le=_SCREEN_MAX)
    frontend_version: str | None = Field(default=None, max_length=_VERSION_MAX)
    bridge_version: str | None = Field(default=None, max_length=_VERSION_MAX)
    # None keeps the details of the previous session.
    device: TerminalDeviceDetailsRequest | None = None


class TerminalDeviceStateResponse(ResponseModel):
    terminal_id: int
    status: TerminalStatusField
    mode: TerminalModeField
    name: str | None
    location: str | None
    pairing_code: str | None
    pairing_expires_at: datetime | None
    infoscreen_id: int | None
    reload_requested_at: datetime | None
    identify_requested_at: datetime | None
    display_power: DisplayPowerField
    # The page asks for its state again at this moment; None when no change
    # is foreseen.
    display_power_changes_at: datetime | None
    # The newest active message to terminals reaching this display.
    broadcast: TerminalBroadcastMessage | None


class TerminalSessionResponse(ResponseModel):
    access_token: str
    expires_at: datetime
    state: TerminalDeviceStateResponse


# ── Admin ─────────────────────────────────────────────────────────────


class TerminalApproveRequest(BaseModel):
    pairing_code: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=200)
    mode: TerminalModeField = "infoscreen"
    infoscreen_id: int | None = None
    location: str | None = Field(default=None, max_length=MAX_LOCATION_LENGTH)


class TerminalUpdateRequest(BaseModel):
    """Only the fields sent change; an explicit null infoscreen_id unassigns
    the screen and an explicit null location clears it."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    mode: TerminalModeField | None = None
    infoscreen_id: int | None = None
    location: str | None = Field(default=None, max_length=MAX_LOCATION_LENGTH)


class TerminalDisplayOverrideRequest(BaseModel):
    power: DisplayPowerField
    # None ends the override at the next change of the screen's schedule;
    # without one foreseen the request is refused.
    until: AwareDatetime | None = None


class TerminalDeviceDetailsResponse(ResponseModel):
    """What the device last reported. computer_serial, display_serial and
    hostname are null for a reader without manage:terminals."""

    computer_model: str | None
    computer_serial: str | None
    ram_mb: int | None
    cpu_temperature_c: float | None
    uptime_seconds: int | None
    kernel: str | None
    os_name: str | None
    hostname: str | None
    under_voltage: bool | None
    throttled: bool | None
    display_make: str | None
    display_model: str | None
    display_serial: str | None
    display_width_px: int | None
    display_height_px: int | None
    display_width_mm: int | None
    display_height_mm: int | None
    display_connector: str | None
    display_connected: bool | None
    display_power_state: str | None
    cec_available: bool | None
    reported_at: datetime


class TerminalBulkActionResponse(ResponseModel):
    """How many terminals an action on all terminals touched."""

    count: int


class TerminalResponse(EntityResponse):
    name: str | None
    status: TerminalStatusField
    mode: TerminalModeField
    pairing_code: str | None
    pairing_expires_at: datetime | None
    infoscreen_id: int | None
    infoscreen_name: str | None
    api_key_id: int | None
    api_key_name: str | None
    # First 16 hex characters of SHA-256 over the raw public key. The
    # fingerprint and both addresses are null for a reader without
    # manage:terminals; identifying_details_visible tells that case apart.
    public_key_fingerprint: str | None
    first_seen_at: datetime
    last_seen_at: datetime
    last_ip: str | None
    # The address the latest access token was issued to.
    last_session_ip: str | None
    identifying_details_visible: bool
    location: str | None
    user_agent: str | None
    screen_width: int | None
    screen_height: int | None
    frontend_version: str | None
    bridge_version: str | None
    device: TerminalDeviceDetailsResponse | None
    approved_at: datetime | None
    approved_by: PublicUserResponse | None
    revoked_at: datetime | None
    reload_requested_at: datetime | None
    identify_requested_at: datetime | None
    duplicate_detected_at: datetime | None
    # Set while an override holds the display on or off.
    display_override: DisplayPowerField | None
    display_override_until: datetime | None
    display_power: DisplayPowerField
    display_power_changes_at: datetime | None


# ── Messages to terminals ─────────────────────────────────────────────


class TerminalBroadcastAudienceRequest(BaseModel):
    """Every terminal (the default), or a pick: the terminals listed plus
    those showing a listed infoscreen. A pick needs at least one id."""

    all_terminals: bool = True
    terminal_ids: list[int] = Field(default_factory=list, max_length=_TARGETS_MAX)
    infoscreen_ids: list[int] = Field(default_factory=list, max_length=_TARGETS_MAX)


class TerminalBroadcastCreateRequest(TerminalBroadcastAudienceRequest):
    # Markdown, rendered on the display.
    text: str = Field(..., min_length=1, max_length=MAX_BROADCAST_TEXT_LENGTH)
    severity: BroadcastSeverityValue = "info"
    style: BroadcastStyleValue = "banner"
    show_until: AwareDatetime


class TerminalBroadcastReachResponse(ResponseModel):
    """Approved terminals an audience reaches now."""

    count: int


class TerminalBroadcastResponse(EntityResponse):
    text: str
    severity: BroadcastSeverityValue
    style: BroadcastStyleValue
    show_until: datetime
    all_terminals: bool
    terminal_ids: list[int]
    infoscreen_ids: list[int]
    created: datetime
    created_by: PublicUserResponse | None
    ended_at: datetime | None
    reach_count: int


# ── Terminal key ──────────────────────────────────────────────────────


class TerminalKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    # None never expires; the security settings' token lifetime cap applies.
    expires_at: AwareDatetime | None = None
