"""
A message to terminals: a one-time text shown as a banner above the screen
or over the whole screen of many displays at once, until `show_until` or
until someone ends it.

The audience is either every terminal or a pick of terminals and of
infoscreens. A terminal is reached when it is picked itself or shows a
picked infoscreen, so an infoscreen pick follows a terminal that is moved to
another screen. Only approved terminals are reached. The author is stored
for the audit trail and never sent to a device.
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime

from src.modules.operations.domain.value_objects.terminal_broadcast import TerminalBroadcastSeverity
from src.modules.operations.domain.value_objects.terminal_broadcast import TerminalBroadcastStyle
from src.modules.platform.domain.entities.user import User
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class TerminalBroadcast(Entity):
    created: datetime
    text: str
    severity: TerminalBroadcastSeverity
    style: TerminalBroadcastStyle
    show_until: datetime
    all_terminals: bool
    created_by_id: int
    terminal_ids: tuple[int, ...] = ()
    infoscreen_ids: tuple[int, ...] = ()
    ended_at: datetime | None = None
    changed: datetime | None = None

    # ── Denormalized (read-only, populated by repository mapper) ──────
    created_by: User | None = field(default=None, compare=False)
