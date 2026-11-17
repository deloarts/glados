"""Rules of messages to terminals: validation, the audience (all, terminals,
infoscreens, both as a union), which message a terminal and a screen preview
show, and ending one."""

from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any

import pytest

from src.modules.operations.domain.entities.terminal import Terminal
from src.modules.operations.domain.entities.terminal_broadcast import TerminalBroadcast
from src.modules.operations.domain.errors import InvalidTerminalBroadcastError
from src.modules.operations.domain.services import terminal_broadcast_rules as rules
from src.modules.operations.domain.value_objects.terminal import TerminalMode
from src.modules.operations.domain.value_objects.terminal import TerminalStatus
from src.modules.operations.domain.value_objects.terminal_broadcast import TerminalBroadcastSeverity
from src.modules.operations.domain.value_objects.terminal_broadcast import TerminalBroadcastStyle

NOW = datetime(2026, 11, 3, 12, tzinfo=UTC)


def _terminal(
    id: int, infoscreen_id: int | None, status: TerminalStatus = TerminalStatus.APPROVED
) -> Terminal:
    return Terminal(
        id=id,
        public_key=f"k{id}",
        public_key_fingerprint="0123456789abcdef",
        status=status,
        mode=TerminalMode.INFOSCREEN,
        name=f"T{id}",
        pairing_code=None,
        pairing_expires_at=None,
        infoscreen_id=infoscreen_id,
        api_key_id=None,
        first_seen_at=NOW,
        last_seen_at=NOW,
    )


def _broadcast(id: int, **overrides: Any) -> TerminalBroadcast:
    fields: dict[str, Any] = {
        "id": id,
        "created": NOW - timedelta(minutes=10 - id),
        "text": f"Message {id}",
        "severity": TerminalBroadcastSeverity.INFO,
        "style": TerminalBroadcastStyle.BANNER,
        "show_until": NOW + timedelta(hours=1),
        "all_terminals": True,
        "created_by_id": 1,
    }
    fields.update(overrides)
    return TerminalBroadcast(**fields)


# Terminal 1 shows screen 10, terminal 2 screen 20, terminal 3 none,
# terminal 4 waits for approval while assigned to screen 10.
TERMINALS = [
    _terminal(1, 10),
    _terminal(2, 20),
    _terminal(3, None),
    _terminal(4, 10, status=TerminalStatus.PENDING),
]


def _reached(**audience: Any) -> list[int]:
    fields: dict[str, Any] = {"all_terminals": False, "terminal_ids": (), "infoscreen_ids": ()}
    fields.update(audience)
    return [t.id for t in rules.reached_terminals(terminals=TERMINALS, **fields)]


def test_terminal_broadcast_audience_all_reaches_every_approved_terminal() -> None:
    assert _reached(all_terminals=True) == [1, 2, 3]


def test_terminal_broadcast_audience_terminal_pick_reaches_unassigned_ones() -> None:
    assert _reached(terminal_ids={3, 4}) == [3]


def test_terminal_broadcast_audience_infoscreen_pick_skips_unassigned_ones() -> None:
    assert _reached(infoscreen_ids={10}) == [1]


def test_terminal_broadcast_audience_both_is_a_union_without_duplicates() -> None:
    assert _reached(terminal_ids={1, 3}, infoscreen_ids={10, 20}) == [1, 2, 3]


def test_terminal_broadcast_infoscreen_pick_follows_a_moved_terminal() -> None:
    broadcast = _broadcast(1, all_terminals=False, infoscreen_ids=(10,))
    terminal = _terminal(1, 10)
    assert rules.newest_for_terminal([broadcast], terminal, NOW) is broadcast
    terminal.infoscreen_id = 20
    assert rules.newest_for_terminal([broadcast], terminal, NOW) is None


def test_terminal_broadcast_newest_active_one_wins() -> None:
    older = _broadcast(1)
    newer = _broadcast(2, all_terminals=False, infoscreen_ids=(10,))
    other = _broadcast(3, all_terminals=False, terminal_ids=(2,))
    assert rules.newest_for_terminal([older, newer, other], TERMINALS[0], NOW) is newer
    assert rules.newest_for_terminal([older, newer, other], TERMINALS[2], NOW) is older
    assert rules.newest_for_terminal([older, newer, other], TERMINALS[3], NOW) is None


def test_terminal_broadcast_expired_or_ended_is_not_active() -> None:
    expired = _broadcast(1, show_until=NOW)
    ended = _broadcast(2, ended_at=NOW - timedelta(minutes=1))
    assert not rules.is_active(expired, NOW)
    assert not rules.is_active(ended, NOW)
    assert rules.newest_for_terminal([expired, ended], TERMINALS[0], NOW) is None


def test_terminal_broadcast_preview_shows_messages_for_all_or_the_screen() -> None:
    to_all = _broadcast(1)
    to_screen = _broadcast(2, all_terminals=False, infoscreen_ids=(10,))
    to_terminal = _broadcast(3, all_terminals=False, terminal_ids=(1,))
    candidates = [to_all, to_screen, to_terminal]
    assert rules.newest_for_infoscreen(candidates, 10, NOW) is to_screen
    assert rules.newest_for_infoscreen(candidates, 20, NOW) is to_all
    assert rules.newest_for_infoscreen([to_terminal], 10, NOW) is None


def test_terminal_broadcast_end_is_idempotent() -> None:
    broadcast = _broadcast(1)
    assert rules.end(broadcast, NOW)
    assert broadcast.ended_at == NOW
    assert not rules.end(broadcast, NOW + timedelta(minutes=1))
    assert broadcast.ended_at == NOW


def test_terminal_broadcast_text_validation() -> None:
    assert rules.normalise_text("  Fire drill at 10:00\n\n**Leave by the north exit**  ") == (
        "Fire drill at 10:00\n\n**Leave by the north exit**"
    )
    with pytest.raises(InvalidTerminalBroadcastError):
        rules.normalise_text("   ")
    with pytest.raises(InvalidTerminalBroadcastError):
        rules.normalise_text("x" * 2001)


def test_terminal_broadcast_show_until_validation() -> None:
    rules.assert_show_until_valid(NOW + timedelta(days=30), NOW)
    with pytest.raises(InvalidTerminalBroadcastError):
        rules.assert_show_until_valid(NOW, NOW)
    with pytest.raises(InvalidTerminalBroadcastError):
        rules.assert_show_until_valid(NOW + timedelta(days=30, seconds=1), NOW)


def test_terminal_broadcast_display_validation() -> None:
    rules.assert_display_valid("danger", "fullscreen")
    with pytest.raises(InvalidTerminalBroadcastError):
        rules.assert_display_valid("success", "banner")
    with pytest.raises(InvalidTerminalBroadcastError):
        rules.assert_display_valid("info", "popup")


@pytest.mark.parametrize(
    "audience",
    [
        {"all_terminals": True, "terminal_ids": [1], "infoscreen_ids": []},
        {"all_terminals": False, "terminal_ids": [], "infoscreen_ids": []},
        {"all_terminals": False, "terminal_ids": [999], "infoscreen_ids": []},
        {"all_terminals": False, "terminal_ids": [], "infoscreen_ids": [99]},
        {"all_terminals": False, "terminal_ids": list(range(501)), "infoscreen_ids": []},
    ],
)
def test_terminal_broadcast_audience_validation_refuses(audience: dict[str, Any]) -> None:
    with pytest.raises(InvalidTerminalBroadcastError):
        rules.assert_audience_valid(
            known_terminal_ids=set(range(501)), known_infoscreen_ids={10, 20}, **audience
        )


def test_terminal_broadcast_audience_validation_accepts_known_picks() -> None:
    # Must not raise: every picked id exists.
    rules.assert_audience_valid(
        all_terminals=False,
        terminal_ids=[1],
        infoscreen_ids=[10],
        known_terminal_ids={1},
        known_infoscreen_ids={10},
    )
