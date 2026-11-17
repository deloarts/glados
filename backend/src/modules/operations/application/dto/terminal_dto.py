"""
Commands and results for terminals: the device sign-in (challenge and
session) with the device details it reports, the state a device reads, the
admin list and its actions, and the terminal key.
"""

from datetime import datetime
from typing import Any
from typing import Literal

from pydantic import AwareDatetime
from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.base import ResultModel
from src.modules.platform.application.dto.user_dto import PublicUserResult

TerminalStatusValue = Literal["pending", "approved", "revoked"]
TerminalModeValue = Literal["infoscreen", "kiosk"]
DisplayPowerValue = Literal["on", "off"]
BroadcastSeverityValue = Literal["info", "warning", "danger"]
BroadcastStyleValue = Literal["banner", "fullscreen"]

# ── Device sign-in ────────────────────────────────────────────────────


class TerminalChallengeResult(ResultModel):
    nonce: str
    expires_at: datetime


class StartTerminalSessionCommand(BaseModel):
    public_key: str
    nonce: str
    signature: str
    user_agent: str | None = None
    screen_width: int | None = None
    screen_height: int | None = None
    frontend_version: str | None = None
    bridge_version: str | None = None
    # The hardware details the bridge reported, as plain data; the domain
    # parser cleans them. None keeps the details of the previous session.
    device: dict[str, Any] | None = None
    # The raw X-Api-Key header, needed only when the device is unknown.
    api_key: str | None = None
    client_ip: str | None = None


class TerminalBroadcastMessage(ResultModel):
    """A message to terminals as a device sees it, without its author."""

    id: int
    text: str
    severity: BroadcastSeverityValue
    style: BroadcastStyleValue
    show_until: datetime


class TerminalDeviceStateResult(ResultModel):
    terminal_id: int
    status: TerminalStatusValue
    mode: TerminalModeValue
    name: str | None
    location: str | None
    pairing_code: str | None
    pairing_expires_at: datetime | None
    infoscreen_id: int | None
    reload_requested_at: datetime | None
    identify_requested_at: datetime | None
    display_power: DisplayPowerValue
    # When the page asks for its state again because the power changes;
    # None when no change is foreseen.
    display_power_changes_at: datetime | None
    # The newest active message reaching this terminal.
    broadcast: TerminalBroadcastMessage | None


class TerminalSessionResult(ResultModel):
    access_token: str
    expires_at: datetime
    state: TerminalDeviceStateResult


# ── Admin ─────────────────────────────────────────────────────────────


class ApproveTerminalCommand(BaseModel):
    pairing_code: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=200)
    mode: TerminalModeValue = "infoscreen"
    infoscreen_id: int | None = None
    location: str | None = None


class UpdateTerminalCommand(BaseModel):
    """Partial update. `fields_set` names the fields the request sent, so an
    explicit null for infoscreen_id unassigns the screen."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    mode: TerminalModeValue | None = None
    infoscreen_id: int | None = None
    # An explicit null clears it.
    location: str | None = None
    fields_set: set[str] = Field(default_factory=set)


class SetDisplayOverrideCommand(BaseModel):
    power: DisplayPowerValue
    # None ends the override at the next change of the screen's schedule.
    until: AwareDatetime | None = None


class TerminalDeviceDetailsResult(ResultModel):
    """What the device last reported about its hardware. The serials and the
    hostname are None for a reader without manage:terminals."""

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


class TerminalBulkResult(ResultModel):
    """How many terminals an action on all terminals touched."""

    count: int


class TerminalResult(ResultBase):
    name: str | None
    status: TerminalStatusValue
    mode: TerminalModeValue
    pairing_code: str | None
    pairing_expires_at: datetime | None
    infoscreen_id: int | None
    infoscreen_name: str | None
    api_key_id: int | None
    api_key_name: str | None
    # The fingerprint and the addresses are None for a reader without
    # manage:terminals; identifying_details_visible says which case it is.
    public_key_fingerprint: str | None
    first_seen_at: datetime
    last_seen_at: datetime
    last_ip: str | None
    last_session_ip: str | None
    identifying_details_visible: bool
    location: str | None
    user_agent: str | None
    screen_width: int | None
    screen_height: int | None
    frontend_version: str | None
    bridge_version: str | None
    device: TerminalDeviceDetailsResult | None
    approved_at: datetime | None
    approved_by: PublicUserResult | None
    revoked_at: datetime | None
    reload_requested_at: datetime | None
    identify_requested_at: datetime | None
    duplicate_detected_at: datetime | None
    display_override: DisplayPowerValue | None
    display_override_until: datetime | None
    display_power: DisplayPowerValue
    display_power_changes_at: datetime | None


# ── Terminal key ──────────────────────────────────────────────────────


class CreateTerminalKeyCommand(BaseModel):
    name: str = Field(..., min_length=1)
    # None never expires; the security settings' token lifetime cap applies.
    expires_at: AwareDatetime | None = None
