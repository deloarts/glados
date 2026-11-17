"""
Converts Terminal entities to the admin result and the device state, and
messages to terminals to what a device and the terminals page see.

The admin result leaves out what identifies one device (the key fingerprint,
the client addresses, the serials and the hostname) unless the reader holds
manage:terminals. The device state and the device's view of a message
carry no person.
"""

from typing import cast

from src.modules.operations.application.dto.terminal_broadcast_dto import TerminalBroadcastResult
from src.modules.operations.application.dto.terminal_dto import BroadcastSeverityValue
from src.modules.operations.application.dto.terminal_dto import BroadcastStyleValue
from src.modules.operations.application.dto.terminal_dto import TerminalBroadcastMessage
from src.modules.operations.application.dto.terminal_dto import TerminalDeviceDetailsResult
from src.modules.operations.application.dto.terminal_dto import TerminalDeviceStateResult
from src.modules.operations.application.dto.terminal_dto import TerminalModeValue
from src.modules.operations.application.dto.terminal_dto import TerminalResult
from src.modules.operations.application.dto.terminal_dto import TerminalStatusValue
from src.modules.operations.domain.entities.terminal import Terminal
from src.modules.operations.domain.entities.terminal_broadcast import TerminalBroadcast
from src.modules.operations.domain.services import display_power_rules
from src.modules.operations.domain.value_objects.display_schedule import DisplayPowerState
from src.modules.operations.domain.value_objects.terminal import TerminalStatus
from src.modules.operations.domain.value_objects.terminal_device_details import (
    device_details_to_data,
)
from src.modules.platform.application.mappers.user_mapper import UserMapper
from src.shared_kernel.domain.services.clock import now_utc


def _device(t: Terminal, identifying: bool) -> TerminalDeviceDetailsResult | None:
    if t.device is None or t.device_reported_at is None:
        return None
    details = t.device if identifying else t.device.without_identifiers()
    return TerminalDeviceDetailsResult(
        **device_details_to_data(details), reported_at=t.device_reported_at
    )


class TerminalMapper:
    @staticmethod
    def to_result(t: Terminal, *, power: DisplayPowerState, identifying: bool) -> TerminalResult:
        """`identifying` says whether the reader holds manage:terminals and
        so may see the fingerprint, the addresses, the serials and the
        hostname."""
        override_active = display_power_rules.override_active(t, now_utc())
        return TerminalResult(
            id=t.id,
            public_id=t.public_id,
            name=t.name,
            status=cast(TerminalStatusValue, t.status),
            mode=cast(TerminalModeValue, t.mode),
            pairing_code=t.pairing_code,
            pairing_expires_at=t.pairing_expires_at,
            infoscreen_id=t.infoscreen_id,
            infoscreen_name=t.infoscreen_name,
            api_key_id=t.api_key_id,
            api_key_name=t.api_key_name,
            public_key_fingerprint=t.public_key_fingerprint if identifying else None,
            first_seen_at=t.first_seen_at,
            last_seen_at=t.last_seen_at,
            last_ip=t.last_ip if identifying else None,
            last_session_ip=t.last_session_ip if identifying else None,
            identifying_details_visible=identifying,
            location=t.location,
            user_agent=t.user_agent,
            screen_width=t.screen_width,
            screen_height=t.screen_height,
            frontend_version=t.frontend_version,
            bridge_version=t.bridge_version,
            device=_device(t, identifying),
            approved_at=t.approved_at,
            approved_by=UserMapper.to_public_result(t.approved_by) if t.approved_by else None,
            revoked_at=t.revoked_at,
            reload_requested_at=t.reload_requested_at,
            identify_requested_at=t.identify_requested_at,
            duplicate_detected_at=t.duplicate_detected_at,
            display_override=(
                t.display_override.value
                if override_active and t.display_override is not None
                else None
            ),
            display_override_until=t.display_override_until if override_active else None,
            display_power=power.power.value,
            display_power_changes_at=power.changes_at,
        )

    @staticmethod
    def to_device_state(
        t: Terminal, *, power: DisplayPowerState, broadcast: TerminalBroadcast | None
    ) -> TerminalDeviceStateResult:
        """What the device itself may see. The pairing code is shown only
        while it waits for approval."""
        pending = t.status == TerminalStatus.PENDING.value
        return TerminalDeviceStateResult(
            terminal_id=t.id,
            status=cast(TerminalStatusValue, t.status),
            mode=cast(TerminalModeValue, t.mode),
            name=t.name,
            location=t.location,
            pairing_code=t.pairing_code if pending else None,
            pairing_expires_at=t.pairing_expires_at if pending else None,
            infoscreen_id=t.infoscreen_id,
            reload_requested_at=t.reload_requested_at,
            identify_requested_at=t.identify_requested_at,
            display_power=power.power.value,
            display_power_changes_at=power.changes_at,
            broadcast=broadcast_message(broadcast) if broadcast is not None else None,
        )


def broadcast_message(b: TerminalBroadcast) -> TerminalBroadcastMessage:
    """A message as a device sees it: text and look, no author."""
    return TerminalBroadcastMessage(
        id=b.id,
        text=b.text,
        severity=cast(BroadcastSeverityValue, b.severity),
        style=cast(BroadcastStyleValue, b.style),
        show_until=b.show_until,
    )


def broadcast_result(b: TerminalBroadcast, reach_count: int) -> TerminalBroadcastResult:
    """A message as the terminals page lists it, with its author."""
    return TerminalBroadcastResult(
        id=b.id,
        public_id=b.public_id,
        text=b.text,
        severity=cast(BroadcastSeverityValue, b.severity),
        style=cast(BroadcastStyleValue, b.style),
        show_until=b.show_until,
        all_terminals=b.all_terminals,
        terminal_ids=list(b.terminal_ids),
        infoscreen_ids=list(b.infoscreen_ids),
        created=b.created,
        created_by=UserMapper.to_public_result(b.created_by) if b.created_by else None,
        ended_at=b.ended_at,
        reach_count=reach_count,
    )
