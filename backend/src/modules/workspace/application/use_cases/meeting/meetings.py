"""
The meetings themselves: list them for a project or a product, read one,
create, edit and delete one, mark it invalid and restore it, create its
follow-up, list the open points it follows up, read its history and
anonymise a guest. Reading needs only a signed-in user, writing
write:meetings, and deleting, marking invalid, restoring and anonymising
manage:meetings.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.edit_version import assert_edit_version
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.workspace.application.dto.meeting_dto import CreateMeetingCommand
from src.modules.workspace.application.dto.meeting_dto import MeetingAttendeeInput
from src.modules.workspace.application.dto.meeting_dto import MeetingEventResult
from src.modules.workspace.application.dto.meeting_dto import MeetingFieldsCommand
from src.modules.workspace.application.dto.meeting_dto import MeetingListQuery
from src.modules.workspace.application.dto.meeting_dto import MeetingListRowResult
from src.modules.workspace.application.dto.meeting_dto import MeetingOpenPointResult
from src.modules.workspace.application.dto.meeting_dto import MeetingResult
from src.modules.workspace.application.dto.meeting_dto import UpdateMeetingCommand
from src.modules.workspace.application.mappers.meeting_mapper import MeetingMapper
from src.modules.workspace.application.mappers.meeting_mapper import card_user_ids
from src.modules.workspace.application.use_cases.meeting._support import MeetingPorts
from src.modules.workspace.application.use_cases.meeting._support import MeetingUseCase
from src.modules.workspace.application.use_cases.meeting._support import load_meeting
from src.modules.workspace.application.use_cases.meeting._support import meeting_result
from src.modules.workspace.application.use_cases.meeting._support import owner_meetings_scope
from src.modules.workspace.application.use_cases.meeting._support import record
from src.modules.workspace.application.use_cases.meeting._support import resolve_attendees
from src.modules.workspace.domain.entities.meeting import Meeting
from src.modules.workspace.domain.errors import MeetingAttendeeNotFoundError
from src.modules.workspace.domain.errors import MeetingInvalidInputError
from src.modules.workspace.domain.errors import MeetingValidityError
from src.modules.workspace.domain.errors import ProductArchivedError
from src.modules.workspace.domain.services.meeting_rules import FOLLOW_UP_DEPTH
from src.modules.workspace.domain.services.meeting_rules import LOCATION_MAX
from src.modules.workspace.domain.services.meeting_rules import NAME_MAX
from src.modules.workspace.domain.services.meeting_rules import REASON_MAX
from src.modules.workspace.domain.services.meeting_rules import MeetingRules
from src.modules.workspace.domain.services.meeting_rules import follow_up_plan
from src.modules.workspace.domain.services.meeting_snapshot_anonymisation import blank_guest
from src.modules.workspace.domain.services.meeting_snapshot_anonymisation import guest_addresses
from src.modules.workspace.domain.services.meeting_tags import normalise_tags
from src.modules.workspace.domain.value_objects.meeting import MeetingAttendeeKind
from src.modules.workspace.domain.value_objects.meeting import MeetingEventKind
from src.shared_kernel.domain.services.clock import now_utc
from src.shared_kernel.domain.services.clock import today_in


def apply_meeting_fields(meeting: Meeting, cmd: MeetingFieldsCommand) -> None:
    MeetingRules.assert_times(cmd.starts_at, cmd.ends_at)
    meeting.name = MeetingRules.required_text(cmd.name, "name", NAME_MAX)
    meeting.starts_at = cmd.starts_at
    meeting.ends_at = cmd.ends_at
    meeting.location = MeetingRules.optional_text(cmd.location, "location", LOCATION_MAX)
    meeting.next_meeting_date = cmd.next_meeting_date
    meeting.next_meeting_time = cmd.next_meeting_time
    meeting.next_meeting_location = MeetingRules.optional_text(
        cmd.next_meeting_location, "next meeting's place", LOCATION_MAX
    )
    if meeting.next_meeting_time is not None and meeting.next_meeting_date is None:
        raise MeetingInvalidInputError("The next meeting's time needs its date.")
    meeting.tags = normalise_tags(cmd.tags)


async def assert_owner_open(
    ports: MeetingPorts, project_id: int | None, product_id: int | None
) -> None:
    """The owner exists, a project is not deleted and a product not archived."""
    await owner_meetings_scope(ports, project_id, product_id, with_projects=False)
    if product_id is not None:
        product = await ports.products.get_by_id(product_id)
        if product is not None and product.archived:
            raise ProductArchivedError(f"Product #{product_id} is archived.")


async def _create(ports: MeetingPorts, actor: User, meeting: Meeting) -> MeetingResult:
    template = (await ports.settings.get_made_items()).meeting_number_format
    # The number is drawn last, after every other read of the write.
    meeting.meeting_number = await ports.meetings.next_number(template)
    saved = await ports.meetings.save(meeting)
    await record(ports, saved.id, MeetingEventKind.CREATED, actor, at=saved.created)
    await ports.uow.commit()
    log.info(f"Created meeting {saved.meeting_number} (ID={saved.id}).")
    return await meeting_result(ports, saved)


class ListMeetings(MeetingUseCase):
    async def execute(self, actor: User, query: MeetingListQuery) -> list[MeetingListRowResult]:
        project_ids, product_ids = await owner_meetings_scope(
            self._ports, query.project_id, query.product_id, with_projects=query.include_projects
        )
        rows = await self._meetings.list_rows(
            project_ids=project_ids,
            product_ids=product_ids,
            include_invalid=query.include_invalid,
            today=today_in(await self._ports.zone()),
            tag=" ".join((query.tag or "").split()) or None,
        )
        user_ids = {
            a.user_id for row in rows for a in row.meeting.attendees if a.user_id is not None
        }
        users = await self._meetings.get_users(user_ids)
        return [MeetingMapper.list_row(row, users) for row in rows]


class GetMeeting(MeetingUseCase):
    async def execute(self, actor: User, meeting_id: int) -> MeetingResult:
        return await meeting_result(self._ports, await load_meeting(self._ports, meeting_id))


class CreateMeeting(MeetingUseCase):
    async def execute(self, actor: User, cmd: CreateMeetingCommand) -> MeetingResult:
        MeetingRules.assert_can_write(actor)
        await assert_owner_open(self._ports, cmd.project_id, cmd.product_id)
        meeting = Meeting(
            id=0,
            meeting_number="",
            name="",
            starts_at=cmd.starts_at,
            ends_at=cmd.ends_at,
            created=now_utc(),
            creator_id=actor.id,
            project_id=cmd.project_id,
            product_id=cmd.product_id,
        )
        apply_meeting_fields(meeting, cmd)
        meeting.attendees = await resolve_attendees(self._ports, cmd.attendees, [])
        return await _create(self._ports, actor, meeting)


class CreateFollowUpMeeting(MeetingUseCase):
    """A meeting of the same owner that follows this one: name, location,
    tags and attendees with their status copied, the agreed next meeting as
    its date, time and place."""

    async def execute(self, actor: User, meeting_id: int) -> MeetingResult:
        MeetingRules.assert_can_write(actor)
        source = await load_meeting(self._ports, meeting_id)
        await assert_owner_open(self._ports, source.project_id, source.product_id)
        plan = follow_up_plan(source, await self._ports.zone())
        meeting = Meeting(
            id=0,
            meeting_number="",
            name=source.name,
            starts_at=plan.starts_at,
            ends_at=plan.ends_at,
            created=now_utc(),
            creator_id=actor.id,
            project_id=source.project_id,
            product_id=source.product_id,
            location=plan.location,
            follow_up_of_id=source.id,
            tags=list(source.tags),
        )
        inputs = [
            MeetingAttendeeInput(
                kind=a.kind,
                status=a.status,
                user_id=a.user_id,
                contact_id=a.contact_id,
                name=a.name,
                email=a.email,
            )
            for a in source.attendees
            if a.anonymised_at is None
        ]
        # A contact archived since keeps its place on the follow-up.
        meeting.attendees = await resolve_attendees(self._ports, inputs, source.attendees)
        for attendee in meeting.attendees:
            attendee.id = 0
        return await _create(self._ports, actor, meeting)


class UpdateMeeting(MeetingUseCase):
    async def execute(
        self, actor: User, meeting_id: int, cmd: UpdateMeetingCommand
    ) -> MeetingResult:
        MeetingRules.assert_can_write(actor)
        await self._meetings.lock_for_update(meeting_id)
        meeting = await load_meeting(self._ports, meeting_id)
        MeetingRules.assert_editable(meeting)
        assert_edit_version(
            meeting, cmd.expected_edit_version, what=f"Meeting {meeting.meeting_number}"
        )
        apply_meeting_fields(meeting, cmd)
        meeting.attendees = await resolve_attendees(self._ports, cmd.attendees, meeting.attendees)
        meeting.changed = now_utc()
        saved = await self._meetings.save(meeting)
        await record(self._ports, saved.id, MeetingEventKind.EDITED, actor, at=meeting.changed)
        await self._uow.commit()
        return await meeting_result(self._ports, saved)


class DeleteMeeting(MeetingUseCase):
    """Soft deletes the meeting. Its rows and files stay until the meeting
    is purged."""

    async def execute(self, actor: User, meeting_id: int, expected_edit_version: int) -> None:
        MeetingRules.assert_can_manage(actor)
        await self._meetings.lock_for_update(meeting_id)
        meeting = await load_meeting(self._ports, meeting_id)
        assert_edit_version(
            meeting, expected_edit_version, what=f"Meeting {meeting.meeting_number}"
        )
        meeting.deleted = True
        meeting.deleted_at = now_utc()
        await self._meetings.save(meeting)
        await self._uow.commit()
        log.info(f"Deleted meeting {meeting.meeting_number} (ID={meeting.id}).")


class MarkMeetingInvalid(MeetingUseCase):
    """Turns the notes read only and takes the meeting's open todos off the
    todo page. The reason is required."""

    async def execute(self, actor: User, meeting_id: int, reason: str) -> MeetingResult:
        MeetingRules.assert_can_manage(actor)
        text = MeetingRules.required_text(reason, "reason", REASON_MAX)
        await self._meetings.lock_for_update(meeting_id)
        meeting = await load_meeting(self._ports, meeting_id)
        if meeting.invalid:
            raise MeetingValidityError(f"Meeting {meeting.meeting_number} is invalid already.")
        now = now_utc()
        meeting.invalid_at, meeting.invalid_by_id, meeting.invalid_reason = now, actor.id, text
        saved = await self._meetings.save(meeting)
        await record(
            self._ports, saved.id, MeetingEventKind.MARKED_INVALID, actor, at=now, summary=text
        )
        await self._uow.commit()
        return await meeting_result(self._ports, saved)


class RestoreMeeting(MeetingUseCase):
    """Makes an invalid meeting valid and editable again, with an optional
    note for the history."""

    async def execute(self, actor: User, meeting_id: int, note: str | None) -> MeetingResult:
        MeetingRules.assert_can_manage(actor)
        text = MeetingRules.optional_text(note, "note", REASON_MAX)
        await self._meetings.lock_for_update(meeting_id)
        meeting = await load_meeting(self._ports, meeting_id)
        if not meeting.invalid:
            raise MeetingValidityError(f"Meeting {meeting.meeting_number} is not invalid.")
        previous = meeting.invalid_reason
        meeting.invalid_at, meeting.invalid_by_id, meeting.invalid_reason = None, None, None
        saved = await self._meetings.save(meeting)
        await record(
            self._ports,
            saved.id,
            MeetingEventKind.RESTORED,
            actor,
            summary=text,
            details={"invalid_reason": previous},
        )
        await self._uow.commit()
        return await meeting_result(self._ports, saved)


class GetMeetingOpenPoints(MeetingUseCase):
    """The open todos of the meeting this one follows and of that meeting's
    own predecessors, nearest first. Invalid and deleted meetings are left
    out but their predecessors are not."""

    async def execute(self, actor: User, meeting_id: int) -> list[MeetingOpenPointResult]:
        meeting = await load_meeting(self._ports, meeting_id)
        chain: list[Meeting] = []
        seen = {meeting.id}
        next_id = meeting.follow_up_of_id
        while next_id is not None and next_id not in seen and len(seen) <= FOLLOW_UP_DEPTH:
            seen.add(next_id)
            previous = await self._meetings.get_by_id(next_id)
            if previous is None:
                break
            if not previous.deleted and not previous.invalid:
                chain.append(previous)
            next_id = previous.follow_up_of_id
        todos = await self._cards.get_open_todos([m.id for m in chain])
        cards = {card.id: card for m in chain for card in await self._cards.get_cards(m.id)}
        users = await self._meetings.get_users(card_user_ids([], [], todos))
        by_meeting = {m.id: m for m in chain}
        order = {m.id: index for index, m in enumerate(chain)}
        todos.sort(key=lambda t: (order[t.meeting_id], cards[t.card_id].position, t.position))
        return [
            MeetingOpenPointResult(
                todo=MeetingMapper.todo(todo, users),
                meeting=MeetingMapper.ref(by_meeting[todo.meeting_id]),
                meeting_starts_at=by_meeting[todo.meeting_id].starts_at,
                card_scope=cards[todo.card_id].scope,
            )
            for todo in todos
        ]


class GetMeetingHistory(MeetingUseCase):
    async def execute(self, actor: User, meeting_id: int) -> list[MeetingEventResult]:
        meeting = await load_meeting(self._ports, meeting_id)
        events = await self._meetings.get_events(meeting.id)
        users = await self._meetings.get_users({e.actor_id for e in events if e.actor_id})
        return [MeetingMapper.event(event, users) for event in events]


class AnonymiseMeetingAttendee(MeetingUseCase):
    """Blanks a guest's name and e-mail address on the meeting and in the
    snapshots of its printed, downloaded and sent notes, where its address
    among the recipients of a send is blanked in the export journal too. The
    checksums of the snapshots stay. A contact is anonymised as a whole from
    the contacts, which reaches its meetings."""

    async def execute(self, actor: User, meeting_id: int, attendee_id: int) -> MeetingResult:
        MeetingRules.assert_can_manage(actor)
        await self._meetings.lock_for_update(meeting_id)
        meeting = await load_meeting(self._ports, meeting_id)
        attendee = next((a for a in meeting.attendees if a.id == attendee_id), None)
        if attendee is None:
            raise MeetingAttendeeNotFoundError(f"Attendee #{attendee_id} not found.")
        if attendee.kind != MeetingAttendeeKind.GUEST:
            raise MeetingInvalidInputError("Only a guest is anonymised on the meeting.")
        if attendee.anonymised_at is None:
            blanked = {attendee.email.casefold()} if attendee.email else set()
            attendee.name, attendee.email, attendee.anonymised_at = "", None, now_utc()
            meeting = await self._meetings.save(meeting)
            await self._blank_snapshots(meeting.id, attendee_id, blanked)
            await self._uow.commit()
            log.info(f"Anonymised guest attendee ID={attendee_id} of meeting ID={meeting.id}.")
        return await meeting_result(self._ports, meeting)

    async def _blank_snapshots(self, meeting_id: int, attendee_id: int, blanked: set[str]) -> None:
        snapshots_repo = self._ports.snapshots
        if snapshots_repo is None:
            return
        snapshots = await snapshots_repo.get_by_meeting(meeting_id)
        for snapshot in snapshots:
            blanked |= guest_addresses(snapshot, attendee_id)
        entry_ids: list[int] = []
        for snapshot in snapshots:
            blank_guest(snapshot, attendee_id, blanked)
            await snapshots_repo.save_copies(snapshot)
            entry_ids.append(snapshot.journal_entry_id)
        if self._ports.journal is not None and entry_ids and blanked:
            await self._ports.journal.anonymise_recipients(entry_ids, blanked)
