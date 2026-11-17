"""
Rules for messages to terminals: what a valid message is, which terminals
it reaches, which message a terminal or a screen preview shows, and ending
one. No I/O.

A message reaches an approved terminal when it goes to every terminal, when
the terminal is picked, or when the terminal shows a picked infoscreen.
Several messages can be active for different audiences; a terminal shows
the newest active one that reaches it.
"""

from collections.abc import Collection
from collections.abc import Iterable
from datetime import datetime

from src.modules.operations.domain.entities.terminal import Terminal
from src.modules.operations.domain.entities.terminal_broadcast import TerminalBroadcast
from src.modules.operations.domain.errors import InvalidTerminalBroadcastError
from src.modules.operations.domain.value_objects.terminal import TerminalStatus
from src.modules.operations.domain.value_objects.terminal_broadcast import MAX_BROADCAST_DURATION
from src.modules.operations.domain.value_objects.terminal_broadcast import MAX_BROADCAST_TARGETS
from src.modules.operations.domain.value_objects.terminal_broadcast import MAX_BROADCAST_TEXT_LENGTH
from src.modules.operations.domain.value_objects.terminal_broadcast import TerminalBroadcastSeverity
from src.modules.operations.domain.value_objects.terminal_broadcast import TerminalBroadcastStyle


def normalise_text(text: str) -> str:
    """The text as shown: trimmed, non-empty and within the cap."""
    text = text.strip()
    if not text:
        raise InvalidTerminalBroadcastError("The message needs a text.")
    if len(text) > MAX_BROADCAST_TEXT_LENGTH:
        raise InvalidTerminalBroadcastError(
            f"The message may have at most {MAX_BROADCAST_TEXT_LENGTH} characters."
        )
    return text


def assert_display_valid(severity: str, style: str) -> None:
    if severity not in TerminalBroadcastSeverity.values():
        raise InvalidTerminalBroadcastError(
            f"severity must be one of {TerminalBroadcastSeverity.values()}."
        )
    if style not in TerminalBroadcastStyle.values():
        raise InvalidTerminalBroadcastError(
            f"style must be one of {TerminalBroadcastStyle.values()}."
        )


def assert_show_until_valid(show_until: datetime, now: datetime) -> None:
    if show_until <= now:
        raise InvalidTerminalBroadcastError("The message must end in the future.")
    if show_until > now + MAX_BROADCAST_DURATION:
        raise InvalidTerminalBroadcastError(
            f"The message may be shown for at most {MAX_BROADCAST_DURATION.days} days."
        )


def assert_audience_valid(
    *,
    all_terminals: bool,
    terminal_ids: Collection[int],
    infoscreen_ids: Collection[int],
    known_terminal_ids: Collection[int],
    known_infoscreen_ids: Collection[int],
) -> None:
    """Every terminal, or a pick of at least one existing terminal or
    infoscreen. A pick together with every terminal is refused, since it
    would mean nothing."""
    if all_terminals:
        if terminal_ids or infoscreen_ids:
            raise InvalidTerminalBroadcastError(
                "A message to every terminal cannot also pick terminals or infoscreens."
            )
        return
    if not terminal_ids and not infoscreen_ids:
        raise InvalidTerminalBroadcastError("Pick at least one terminal or infoscreen.")
    if len(terminal_ids) > MAX_BROADCAST_TARGETS or len(infoscreen_ids) > MAX_BROADCAST_TARGETS:
        raise InvalidTerminalBroadcastError(
            f"A message may pick at most {MAX_BROADCAST_TARGETS} terminals and "
            f"{MAX_BROADCAST_TARGETS} infoscreens."
        )
    unknown_terminals = sorted(set(terminal_ids) - set(known_terminal_ids))
    if unknown_terminals:
        raise InvalidTerminalBroadcastError(f"Unknown terminal(s) {unknown_terminals}.")
    unknown_screens = sorted(set(infoscreen_ids) - set(known_infoscreen_ids))
    if unknown_screens:
        raise InvalidTerminalBroadcastError(f"Unknown infoscreen(s) {unknown_screens}.")


def is_active(broadcast: TerminalBroadcast, now: datetime) -> bool:
    return broadcast.ended_at is None and now < broadcast.show_until


def reaches(
    *,
    all_terminals: bool,
    terminal_ids: Collection[int],
    infoscreen_ids: Collection[int],
    terminal: Terminal,
) -> bool:
    """Whether an audience reaches the terminal as it is now."""
    if terminal.status != TerminalStatus.APPROVED.value:
        return False
    return (
        all_terminals
        or terminal.id in terminal_ids
        or (terminal.infoscreen_id is not None and terminal.infoscreen_id in infoscreen_ids)
    )


def reached_terminals(
    *,
    all_terminals: bool,
    terminal_ids: Collection[int],
    infoscreen_ids: Collection[int],
    terminals: Iterable[Terminal],
) -> list[Terminal]:
    """The terminals an audience reaches now, each once."""
    return [
        t
        for t in terminals
        if reaches(
            all_terminals=all_terminals,
            terminal_ids=terminal_ids,
            infoscreen_ids=infoscreen_ids,
            terminal=t,
        )
    ]


def _newest(candidates: Iterable[TerminalBroadcast]) -> TerminalBroadcast | None:
    return max(candidates, key=lambda b: (b.created, b.id), default=None)


def newest_for_terminal(
    broadcasts: Iterable[TerminalBroadcast], terminal: Terminal, now: datetime
) -> TerminalBroadcast | None:
    """The message the terminal shows now: the newest active one reaching it."""
    return _newest(
        b
        for b in broadcasts
        if is_active(b, now)
        and reaches(
            all_terminals=b.all_terminals,
            terminal_ids=b.terminal_ids,
            infoscreen_ids=b.infoscreen_ids,
            terminal=terminal,
        )
    )


def newest_for_infoscreen(
    broadcasts: Iterable[TerminalBroadcast], infoscreen_id: int, now: datetime
) -> TerminalBroadcast | None:
    """The message a preview of the screen shows: the newest active one that
    goes to every terminal or picks the screen."""
    return _newest(
        b
        for b in broadcasts
        if is_active(b, now) and (b.all_terminals or infoscreen_id in b.infoscreen_ids)
    )


def end(broadcast: TerminalBroadcast, now: datetime) -> bool:
    """Ends an active message now. Ending one that already ended or ran out
    changes nothing; returns whether it changed."""
    if not is_active(broadcast, now):
        return False
    broadcast.ended_at = now
    broadcast.changed = now
    return True
