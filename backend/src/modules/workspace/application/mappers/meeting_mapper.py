"""
Converts meetings and the rows that belong to them into their result DTOs.
The users they name are resolved once per request and handed in as a map.
"""

from collections.abc import Mapping

from src.modules.platform.application.dto.user_dto import PublicUserResult
from src.modules.platform.application.mappers.user_mapper import UserMapper
from src.modules.platform.domain.entities.user import User
from src.modules.workspace.application.dto.meeting_dto import MeetingAttendeeChipResult
from src.modules.workspace.application.dto.meeting_dto import MeetingAttendeeResult
from src.modules.workspace.application.dto.meeting_dto import MeetingCardResult
from src.modules.workspace.application.dto.meeting_dto import MeetingCardRevisionResult
from src.modules.workspace.application.dto.meeting_dto import MeetingDecisionResult
from src.modules.workspace.application.dto.meeting_dto import MeetingEventResult
from src.modules.workspace.application.dto.meeting_dto import MeetingFileResult
from src.modules.workspace.application.dto.meeting_dto import MeetingListRowResult
from src.modules.workspace.application.dto.meeting_dto import MeetingOwnerResult
from src.modules.workspace.application.dto.meeting_dto import MeetingRefResult
from src.modules.workspace.application.dto.meeting_dto import MeetingResult
from src.modules.workspace.application.dto.meeting_dto import MeetingScopeChipResult
from src.modules.workspace.application.dto.meeting_dto import MeetingTodoOwnerResult
from src.modules.workspace.application.dto.meeting_dto import MeetingTodoResult
from src.modules.workspace.domain.entities.meeting import Meeting
from src.modules.workspace.domain.entities.meeting import MeetingAttendee
from src.modules.workspace.domain.entities.meeting import MeetingCard
from src.modules.workspace.domain.entities.meeting import MeetingCardRevision
from src.modules.workspace.domain.entities.meeting import MeetingDecision
from src.modules.workspace.domain.entities.meeting import MeetingEvent
from src.modules.workspace.domain.entities.meeting import MeetingTodo
from src.modules.workspace.domain.services.meeting_markdown import plain_excerpt
from src.modules.workspace.ports.outbound.repositories.meeting_repository import MeetingListRow

Users = Mapping[int, User]


def _user(users: Users, user_id: int | None) -> PublicUserResult | None:
    if user_id is None:
        return None
    user = users.get(user_id)
    return UserMapper.to_public_result(user) if user is not None else None


def meeting_user_ids(meeting: Meeting) -> set[int]:
    ids = {meeting.creator_id}
    ids.update(i for i in (meeting.changed_by_id, meeting.invalid_by_id) if i is not None)
    ids.update(a.user_id for a in meeting.attendees if a.user_id is not None)
    return ids


def card_user_ids(
    cards: list[MeetingCard], decisions: list[MeetingDecision], todos: list[MeetingTodo]
) -> set[int]:
    ids: set[int] = set()
    for card in cards:
        ids.add(card.creator_id)
        if card.changed_by_id is not None:
            ids.add(card.changed_by_id)
    ids.update(decision.creator_id for decision in decisions)
    for todo in todos:
        ids.add(todo.creator_id)
        if todo.done_by_id is not None:
            ids.add(todo.done_by_id)
        ids.update(todo.owner_user_ids)
    return ids


class MeetingMapper:
    @staticmethod
    def owner(meeting: Meeting) -> MeetingOwnerResult:
        return MeetingOwnerResult(
            kind=meeting.owner_kind,
            id=meeting.owner_id,
            number=meeting.owner_number,
            product_id=meeting.owner_product_id,
        )

    @staticmethod
    def ref(meeting: Meeting) -> MeetingRefResult:
        return MeetingRefResult(
            id=meeting.id, meeting_number=meeting.meeting_number, name=meeting.name
        )

    @staticmethod
    def attendee_name(attendee: MeetingAttendee, users: Users) -> str:
        if attendee.user_id is not None:
            user = users.get(attendee.user_id)
            return user.full_name if user is not None else ""
        return attendee.name or ""

    @staticmethod
    def attendee_email(attendee: MeetingAttendee, users: Users) -> str | None:
        """A user's current address, or the copy kept for a contact or a guest.
        The meeting shows how to reach every attendee, colleagues included."""
        if attendee.user_id is not None:
            user = users.get(attendee.user_id)
            return user.email if user is not None else None
        return attendee.email

    @staticmethod
    def attendee(attendee: MeetingAttendee, users: Users) -> MeetingAttendeeResult:
        return MeetingAttendeeResult(
            id=attendee.id,
            public_id=attendee.public_id,
            kind=attendee.kind,
            status=attendee.status,
            position=attendee.position,
            user=_user(users, attendee.user_id),
            contact_id=attendee.contact_id,
            name=MeetingMapper.attendee_name(attendee, users),
            email=MeetingMapper.attendee_email(attendee, users),
            anonymised=attendee.anonymised_at is not None,
        )

    @staticmethod
    def todo(todo: MeetingTodo, users: Users) -> MeetingTodoResult:
        return MeetingTodoResult(
            id=todo.id,
            public_id=todo.public_id,
            meeting_id=todo.meeting_id,
            card_id=todo.card_id,
            position=todo.position,
            title=todo.title,
            note=todo.note,
            due_date=todo.due_date,
            done=todo.done,
            done_at=todo.done_at,
            done_by=_user(users, todo.done_by_id),
            created=todo.created,
            creator=_user(users, todo.creator_id),
            changed=todo.changed,
            owners=[
                MeetingTodoOwnerResult(
                    user=_user(users, owner.user_id),
                    contact_id=owner.contact_id,
                    name=(
                        users[owner.user_id].full_name
                        if owner.user_id is not None and owner.user_id in users
                        else owner.name or ""
                    ),
                )
                for owner in todo.owners
            ],
        )

    @staticmethod
    def decision(decision: MeetingDecision, users: Users) -> MeetingDecisionResult:
        return MeetingDecisionResult(
            id=decision.id,
            public_id=decision.public_id,
            meeting_id=decision.meeting_id,
            card_id=decision.card_id,
            position=decision.position,
            text=decision.text,
            created=decision.created,
            creator=_user(users, decision.creator_id),
        )

    @staticmethod
    def card(
        card: MeetingCard,
        decisions: list[MeetingDecision],
        todos: list[MeetingTodo],
        users: Users,
    ) -> MeetingCardResult:
        return MeetingCardResult(
            id=card.id,
            public_id=card.public_id,
            meeting_id=card.meeting_id,
            position=card.position,
            scope=card.scope,
            scope_icon=card.scope_icon,
            body=card.body,
            internal=card.internal,
            created=card.created,
            creator=_user(users, card.creator_id),
            changed=card.changed,
            changed_by=_user(users, card.changed_by_id),
            edit_version=card.edit_version,
            decisions=[MeetingMapper.decision(d, users) for d in decisions if d.card_id == card.id],
            todos=[MeetingMapper.todo(t, users) for t in todos if t.card_id == card.id],
        )

    @staticmethod
    def meeting(
        meeting: Meeting,
        *,
        follow_up_of: Meeting | None,
        cards: list[MeetingCardResult],
        files: list[MeetingFileResult],
        users: Users,
    ) -> MeetingResult:
        return MeetingResult(
            id=meeting.id,
            public_id=meeting.public_id,
            meeting_number=meeting.meeting_number,
            owner=MeetingMapper.owner(meeting),
            name=meeting.name,
            starts_at=meeting.starts_at,
            ends_at=meeting.ends_at,
            location=meeting.location,
            next_meeting_date=meeting.next_meeting_date,
            next_meeting_time=meeting.next_meeting_time,
            next_meeting_location=meeting.next_meeting_location,
            follow_up_of=MeetingMapper.ref(follow_up_of) if follow_up_of is not None else None,
            valid=not meeting.invalid,
            invalid_at=meeting.invalid_at,
            invalid_by=_user(users, meeting.invalid_by_id),
            invalid_reason=meeting.invalid_reason,
            issue_number=meeting.issue_number,
            last_sent_at=meeting.last_sent_at,
            last_printed_at=meeting.last_printed_at,
            created=meeting.created,
            creator=_user(users, meeting.creator_id),
            changed=meeting.changed,
            changed_by=_user(users, meeting.changed_by_id),
            edit_version=meeting.edit_version,
            attendees=[MeetingMapper.attendee(a, users) for a in meeting.attendees],
            tags=list(meeting.tags),
            cards=cards,
            files=files,
        )

    @staticmethod
    def list_row(row: MeetingListRow, users: Users) -> MeetingListRowResult:
        meeting = row.meeting
        return MeetingListRowResult(
            id=meeting.id,
            public_id=meeting.public_id,
            meeting_number=meeting.meeting_number,
            owner=MeetingMapper.owner(meeting),
            name=meeting.name,
            valid=not meeting.invalid,
            starts_at=meeting.starts_at,
            ends_at=meeting.ends_at,
            location=meeting.location,
            scopes=[
                MeetingScopeChipResult(scope=c.scope, icon=c.icon, internal=c.internal)
                for c in row.cards
            ],
            notes=plain_excerpt(row.bodies),
            attendees=[
                MeetingAttendeeChipResult(
                    kind=a.kind,
                    status=a.status,
                    user_id=a.user_id,
                    name=MeetingMapper.attendee_name(a, users),
                )
                for a in meeting.attendees
            ],
            tags=list(meeting.tags),
            open_todo_count=row.open_todo_count,
            overdue_todo_count=row.overdue_todo_count,
            sent=meeting.last_sent_at is not None,
            printed=meeting.last_printed_at is not None,
        )

    @staticmethod
    def event(event: MeetingEvent, users: Users) -> MeetingEventResult:
        return MeetingEventResult(
            id=event.id,
            public_id=event.public_id,
            meeting_id=event.meeting_id,
            kind=event.kind,
            at=event.at,
            actor=_user(users, event.actor_id),
            card_id=event.card_id,
            todo_id=event.todo_id,
            file_id=event.file_id,
            summary=event.summary,
            details=event.details,
        )

    @staticmethod
    def revision(revision: MeetingCardRevision, users: Users) -> MeetingCardRevisionResult:
        return MeetingCardRevisionResult(
            id=revision.id,
            public_id=revision.public_id,
            card_id=revision.card_id,
            scope=revision.scope,
            scope_icon=revision.scope_icon,
            body=revision.body,
            internal=revision.internal,
            author=_user(users, revision.author_id),
            created=revision.created,
            saved_at=revision.saved_at,
        )
