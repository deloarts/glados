"""
The pure rules of meetings: when a card save updates the author's last
revision, where a follow-up takes place, the sentence of a bundled
notification, and the ranking and near duplicates of scopes.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta
from zoneinfo import ZoneInfo

from src.modules.platform.domain.value_objects.language import Language
from src.modules.workspace.adapters.outbound.locale.meeting_activity_phrases import (
    meeting_activity_phrases,
)
from src.modules.workspace.domain.entities.meeting import Meeting
from src.modules.workspace.domain.entities.meeting import MeetingCardRevision
from src.modules.workspace.domain.services.meeting_rules import MeetingRules
from src.modules.workspace.domain.services.meeting_rules import follow_up_plan
from src.modules.workspace.domain.services.meeting_rules import meeting_activity_message
from src.modules.workspace.domain.services.meeting_rules import meeting_activity_title
from src.modules.workspace.domain.services.meeting_scopes import ScopeUse
from src.modules.workspace.domain.services.meeting_scopes import near_duplicate
from src.modules.workspace.domain.services.meeting_scopes import ranked
from src.modules.workspace.domain.value_objects.meeting import MeetingScopeIcon

_VIENNA = ZoneInfo("Europe/Vienna")
_START = datetime(2026, 11, 6, 8, 0, tzinfo=UTC)


def _meeting(**fields: object) -> Meeting:
    return Meeting(
        id=1,
        meeting_number="MTG-26-0021",
        name="Review",
        starts_at=_START,
        ends_at=_START + timedelta(minutes=90),
        created=_START,
        creator_id=1,
        project_id=1,
        location="Room Danube",
        **fields,  # type: ignore[arg-type]
    )


def _revision(author_id: int, created: datetime) -> MeetingCardRevision:
    return MeetingCardRevision(
        id=1,
        card_id=1,
        scope=None,
        scope_icon=None,
        body="",
        internal=False,
        author_id=author_id,
        created=created,
        saved_at=created,
    )


def test_meeting_rules_merge_saves_of_one_author_within_ten_minutes() -> None:
    last = _revision(7, _START)

    assert MeetingRules.merges_into(last, 7, _START + timedelta(minutes=10))
    assert not MeetingRules.merges_into(last, 7, _START + timedelta(minutes=11))
    assert not MeetingRules.merges_into(last, 8, _START + timedelta(minutes=1))
    assert not MeetingRules.merges_into(None, 7, _START)


def test_meeting_rules_follow_up_takes_the_next_meeting_in_the_tenant_zone() -> None:
    plan = follow_up_plan(
        _meeting(
            next_meeting_date=date(2026, 11, 20),
            next_meeting_time=time(10, 0),
            next_meeting_location="Teams",
        ),
        _VIENNA,
    )

    assert plan.starts_at == datetime(2026, 11, 20, 9, 0, tzinfo=UTC)
    assert plan.ends_at - plan.starts_at == timedelta(minutes=90)
    assert plan.location == "Teams"


def test_meeting_rules_follow_up_without_a_next_meeting_is_a_week_later() -> None:
    plan = follow_up_plan(_meeting(), _VIENNA)

    assert plan.starts_at == _START + timedelta(days=7)
    assert plan.location == "Room Danube"


def test_meeting_rules_activity_message_counts_mentions_and_todos() -> None:
    english = meeting_activity_phrases()[Language.enGB]
    assert (
        meeting_activity_message(english, ["Jonas"], 2, 2, "MTG-26-0021")
        == "Jonas mentioned you twice and assigned you 2 todos in MTG-26-0021"
    )
    assert (
        meeting_activity_message(english, ["Jonas", "Anna", "Lena"], 1, 0, "MTG-1")
        == "Jonas, Anna and Lena mentioned you once in MTG-1"
    )
    assert (
        meeting_activity_message(english, [], 0, 1, "MTG-1")
        == "Someone assigned you 1 todo in MTG-1"
    )


def test_meeting_rules_activity_message_and_title_follow_a_german_recipient() -> None:
    """The German sentences come from the de-AT locale data file: the verb
    follows the number of actors and the counted phrases their own forms."""
    german = meeting_activity_phrases()[Language.deAT]
    one, several = german.one_actor, german.several_actors
    assert meeting_activity_message(german, ["Jonas"], 2, 2, "MTG-26-0021") == (
        one.mentions_and_todos.format(
            names="Jonas",
            times=german.twice,
            todos=german.todos.format(count=2),
            meeting="MTG-26-0021",
        )
    )
    assert meeting_activity_message(german, ["Jonas", "Anna", "Lena"], 3, 0, "MTG-1") == (
        several.mentions.format(
            names=f"Jonas{german.list_separator}Anna{german.last_separator}Lena",
            times=german.times.format(count=3),
            todos="",
            meeting="MTG-1",
        )
    )
    assert meeting_activity_message(german, [], 0, 1, "MTG-1") == one.todos.format(
        names=german.someone, times="", todos=german.one_todo, meeting="MTG-1"
    )
    assert meeting_activity_title(german, "MTG-1") == german.title.format(meeting="MTG-1")
    assert german != meeting_activity_phrases()[Language.enGB]
    assert meeting_activity_title(meeting_activity_phrases()[Language.enGB], "MTG-1") == (
        "Activity in MTG-1"
    )


def test_every_shipped_language_has_its_meeting_activity_phrases() -> None:
    assert set(meeting_activity_phrases()) == set(Language)


def test_meeting_scopes_near_duplicate_ignores_case_spacing_and_small_typos() -> None:
    uses = [
        ScopeUse("Vacuum gripper", 5, MeetingScopeIcon.MECHANICS),
        ScopeUse("Schedule", 2, None),
    ]

    assert near_duplicate("vacuum  GRIPPER", uses) == "Vacuum gripper"
    assert near_duplicate("Vacum gripper", uses) == "Vacuum gripper"
    assert near_duplicate("Shcedule", uses) == "Schedule"
    assert near_duplicate("Vacuum gripper", uses) is None
    assert near_duplicate("Safety", uses) is None


def test_meeting_scopes_rank_by_use_then_name() -> None:
    uses = [ScopeUse("b", 1, None), ScopeUse("a", 1, None), ScopeUse("c", 3, None)]

    assert [u.scope for u in ranked(uses, None, 10)] == ["c", "a", "b"]
    assert [u.scope for u in ranked(uses, "A", 10)] == ["a"]
