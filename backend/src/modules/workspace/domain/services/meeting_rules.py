"""
Pure rules for meetings: who may change them, the values a meeting and its
cards, decisions, todos and attendees accept, when a card save updates the
author's last revision, where a follow-up meeting takes place, and the
title and sentence a bundled notification reads, put together from the
phrases of the recipient's language. No I/O.
"""

from dataclasses import dataclass
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta
from datetime import tzinfo

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.domain.entities.meeting import Meeting
from src.modules.workspace.domain.entities.meeting import MeetingCardRevision
from src.modules.workspace.domain.entities.meeting import MeetingTodo
from src.modules.workspace.domain.errors import MeetingInvalidInputError
from src.modules.workspace.domain.errors import MeetingReadOnlyError
from src.modules.workspace.domain.value_objects.meeting_activity_phrases import (
    MeetingActivityPhrases,
)

NAME_MAX = 200
LOCATION_MAX = 200
SCOPE_MAX = 80
BODY_MAX = 100_000
TODO_TITLE_MAX = 300
TODO_NOTE_MAX = 4_000
DECISION_MAX = 2_000
REASON_MAX = 1_000
ATTENDEES_MAX = 100

# A save by the author of a card's last revision within this time of the
# revision's start updates that revision instead of adding one.
REVISION_MERGE_WINDOW = timedelta(minutes=10)

# How long the mentions and todo assignments of a meeting wait for a
# recipient before they go out as one notification.
NOTIFICATION_DELAY = timedelta(minutes=5)

# How far a follow-up looks back through the meetings it follows.
FOLLOW_UP_DEPTH = 50


class MeetingRules:
    # ── Permissions ───────────────────────────────────────────────────

    @staticmethod
    def assert_can_write(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_MEETINGS, "edit", "meetings")

    @staticmethod
    def assert_can_manage(actor: User) -> None:
        assert_has_permission(actor, Permission.MANAGE_MEETINGS, "manage", "meetings")

    @staticmethod
    def assert_can_tick(actor: User, todo: MeetingTodo) -> None:
        """A writer of meetings ticks any todo off, and an owner of a todo
        ticks off their own, which the todo page offers to everyone."""
        if actor.has_permission(Permission.WRITE_MEETINGS) or actor.id in todo.owner_user_ids:
            return
        raise InsufficientPermissionsError(
            f"User #{actor.id} ({actor.full_name}) cannot tick off todo #{todo.id}."
        )

    @staticmethod
    def assert_editable(meeting: Meeting) -> None:
        if meeting.invalid:
            raise MeetingReadOnlyError(
                f"Meeting {meeting.meeting_number} is marked invalid and cannot be changed."
            )

    # ── Values ────────────────────────────────────────────────────────

    @staticmethod
    def required_text(value: str, what: str, limit: int) -> str:
        text = value.strip()
        if not text:
            raise MeetingInvalidInputError(f"The {what} must not be empty.")
        if len(text) > limit:
            raise MeetingInvalidInputError(f"The {what} must be at most {limit} characters.")
        return text

    @staticmethod
    def optional_text(value: str | None, what: str, limit: int) -> str | None:
        if value is None:
            return None
        text = value.strip()
        if len(text) > limit:
            raise MeetingInvalidInputError(f"The {what} must be at most {limit} characters.")
        return text or None

    @staticmethod
    def assert_owner(project_id: int | None, product_id: int | None) -> None:
        if (project_id is None) == (product_id is None):
            raise MeetingInvalidInputError("A meeting belongs to exactly one project or product.")

    @staticmethod
    def assert_times(starts_at: datetime, ends_at: datetime) -> None:
        if starts_at.tzinfo is None or ends_at.tzinfo is None:
            raise MeetingInvalidInputError("Start and end must carry a time zone.")
        if ends_at < starts_at:
            raise MeetingInvalidInputError("A meeting cannot end before it starts.")

    @staticmethod
    def assert_body(body: str) -> None:
        if len(body) > BODY_MAX:
            raise MeetingInvalidInputError(f"A card's text must be at most {BODY_MAX} characters.")

    @staticmethod
    def merges_into(last: MeetingCardRevision | None, actor_id: int, now: datetime) -> bool:
        """Whether a save updates the card's last revision: the same author
        saves within the merge window of the revision's start."""
        return (
            last is not None
            and last.author_id == actor_id
            and now - last.created <= REVISION_MERGE_WINDOW
        )


@dataclass(frozen=True)
class FollowUpPlan:
    starts_at: datetime
    ends_at: datetime
    location: str | None


def follow_up_plan(meeting: Meeting, zone: tzinfo) -> FollowUpPlan:
    """Where and when a follow-up of the meeting takes place: on the agreed
    next meeting's date and time, at its place, for as long as the meeting
    lasted. A next meeting without a time keeps the meeting's start time,
    and without a date the follow-up is one week after the meeting."""
    duration = meeting.ends_at - meeting.starts_at
    local_start = meeting.starts_at.astimezone(zone)
    day: date = meeting.next_meeting_date or (local_start + timedelta(days=7)).date()
    wall: time = meeting.next_meeting_time or local_start.time()
    starts_at = datetime.combine(day, wall, tzinfo=zone).astimezone(UTC)
    location = meeting.next_meeting_location or meeting.location
    return FollowUpPlan(starts_at=starts_at, ends_at=starts_at + duration, location=location)


def _times(count: int, phrases: MeetingActivityPhrases) -> str:
    if count == 1:
        return phrases.once
    if count == 2:
        return phrases.twice
    return phrases.times.format(count=count)


def _todos(count: int, phrases: MeetingActivityPhrases) -> str:
    return phrases.one_todo if count == 1 else phrases.todos.format(count=count)


def _names(names: list[str], phrases: MeetingActivityPhrases) -> str:
    if not names:
        return phrases.someone
    if len(names) == 1:
        return names[0]
    return phrases.list_separator.join(names[:-1]) + phrases.last_separator + names[-1]


def meeting_activity_message(
    phrases: MeetingActivityPhrases,
    actor_names: list[str],
    mention_count: int,
    todo_count: int,
    meeting_number: str,
) -> str:
    """The sentence of a bundled notification in the language of `phrases`,
    such as "Jonas mentioned you twice and assigned you 2 todos in
    MTG-26-0021". An entry without mentions reads as the todo sentence."""
    sentences = phrases.several_actors if len(actor_names) > 1 else phrases.one_actor
    if mention_count and todo_count:
        template = sentences.mentions_and_todos
    elif mention_count:
        template = sentences.mentions
    else:
        template = sentences.todos
    return template.format(
        names=_names(actor_names, phrases),
        times=_times(mention_count, phrases),
        todos=_todos(todo_count, phrases),
        meeting=meeting_number,
    )


def meeting_activity_title(phrases: MeetingActivityPhrases, meeting_number: str) -> str:
    """The title of a bundled notification in the language of `phrases`."""
    return phrases.title.format(meeting=meeting_number)
