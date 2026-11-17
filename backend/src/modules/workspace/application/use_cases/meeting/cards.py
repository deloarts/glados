"""
The cards of a meeting: read one, add, save, delete and reorder them, list
a card's revisions and restore one, and announce that someone edits a card.
Each card saves on its own with its edit version, so several people can
write different cards at once; a save of a card that moved since answers
409. Writing needs write:meetings and a meeting that is not invalid.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.edit_version import assert_edit_version
from src.modules.workspace.application.dto.meeting_dto import MeetingCardCommand
from src.modules.workspace.application.dto.meeting_dto import MeetingCardResult
from src.modules.workspace.application.dto.meeting_dto import MeetingCardRevisionResult
from src.modules.workspace.application.mappers.meeting_mapper import MeetingMapper
from src.modules.workspace.application.use_cases.meeting._support import MeetingPorts
from src.modules.workspace.application.use_cases.meeting._support import MeetingUseCase
from src.modules.workspace.application.use_cases.meeting._support import card_label
from src.modules.workspace.application.use_cases.meeting._support import card_result
from src.modules.workspace.application.use_cases.meeting._support import card_results
from src.modules.workspace.application.use_cases.meeting._support import load_card
from src.modules.workspace.application.use_cases.meeting._support import load_meeting
from src.modules.workspace.application.use_cases.meeting._support import record
from src.modules.workspace.application.use_cases.meeting._support import save_card_content
from src.modules.workspace.domain.entities.meeting import Meeting
from src.modules.workspace.domain.entities.meeting import MeetingCard
from src.modules.workspace.domain.errors import MeetingCardRevisionNotFoundError
from src.modules.workspace.domain.errors import MeetingInvalidInputError
from src.modules.workspace.domain.services.meeting_rules import MeetingRules
from src.modules.workspace.domain.value_objects.meeting import MeetingEventKind
from src.modules.workspace.ports.outbound.meeting_presence_port import IMeetingPresence
from src.shared_kernel.domain.services.clock import now_utc


async def _writable(ports: MeetingPorts, actor: User, meeting_id: int) -> Meeting:
    MeetingRules.assert_can_write(actor)
    meeting = await load_meeting(ports, meeting_id)
    MeetingRules.assert_editable(meeting)
    return meeting


class GetMeetingCard(MeetingUseCase):
    async def execute(self, actor: User, meeting_id: int, card_id: int) -> MeetingCardResult:
        meeting = await load_meeting(self._ports, meeting_id)
        return await card_result(self._ports, await load_card(self._ports, meeting, card_id))


class CreateMeetingCard(MeetingUseCase):
    async def execute(
        self, actor: User, meeting_id: int, cmd: MeetingCardCommand
    ) -> MeetingCardResult:
        meeting = await _writable(self._ports, actor, meeting_id)
        card = MeetingCard(
            id=0,
            meeting_id=meeting.id,
            position=await self._cards.next_position(meeting.id),
            scope=None,
            scope_icon=None,
            body="",
            internal=False,
            created=now_utc(),
            creator_id=actor.id,
        )
        saved = await save_card_content(
            self._ports,
            actor,
            card,
            scope=cmd.scope,
            scope_icon=cmd.scope_icon,
            body=cmd.body,
            internal=cmd.internal,
        )
        await record(
            self._ports,
            meeting.id,
            MeetingEventKind.CARD_ADDED,
            actor,
            card_id=saved.card.id,
            summary=card_label(saved.card),
            details={"internal": saved.card.internal},
        )
        await self._uow.commit()
        return await card_result(self._ports, saved.card)


class UpdateMeetingCard(MeetingUseCase):
    """Saves the card's scope, icon, text and internal flag. A save by the
    author of the card's last revision within ten minutes of its start
    updates that revision; any other save starts one and is a history
    event."""

    async def execute(
        self, actor: User, meeting_id: int, card_id: int, cmd: MeetingCardCommand
    ) -> MeetingCardResult:
        meeting = await _writable(self._ports, actor, meeting_id)
        await self._cards.lock_card(card_id)
        card = await load_card(self._ports, meeting, card_id)
        assert_edit_version(card, cmd.expected_edit_version, what=f"Card #{card.id}")
        saved = await save_card_content(
            self._ports,
            actor,
            card,
            scope=cmd.scope,
            scope_icon=cmd.scope_icon,
            body=cmd.body,
            internal=cmd.internal,
        )
        if saved.new_revision:
            await record(
                self._ports,
                meeting.id,
                MeetingEventKind.CARD_CHANGED,
                actor,
                card_id=card.id,
                summary=card_label(saved.card),
            )
        await self._uow.commit()
        return await card_result(self._ports, saved.card)


class DeleteMeetingCard(MeetingUseCase):
    """Removes the card with its revisions, decisions and todos. Its files
    stay on the meeting."""

    async def execute(
        self, actor: User, meeting_id: int, card_id: int, expected_edit_version: int
    ) -> None:
        meeting = await _writable(self._ports, actor, meeting_id)
        await self._cards.lock_card(card_id)
        card = await load_card(self._ports, meeting, card_id)
        assert_edit_version(card, expected_edit_version, what=f"Card #{card.id}")
        await self._cards.delete_card(card)
        await record(
            self._ports,
            meeting.id,
            MeetingEventKind.CARD_DELETED,
            actor,
            card_id=card.id,
            summary=card_label(card),
        )
        await self._uow.commit()


class ReorderMeetingCards(MeetingUseCase):
    """Puts the cards in the given order, which names every card of the
    meeting once. Reordering moves no card's edit version."""

    async def execute(
        self, actor: User, meeting_id: int, card_ids: list[int]
    ) -> list[MeetingCardResult]:
        meeting = await _writable(self._ports, actor, meeting_id)
        current = {card.id for card in await self._cards.get_cards(meeting.id)}
        if len(card_ids) != len(set(card_ids)) or set(card_ids) != current:
            raise MeetingInvalidInputError("The order must name every card of the meeting once.")
        await self._cards.set_positions(meeting.id, card_ids)
        await self._uow.commit()
        return await card_results(self._ports, meeting.id)


class GetMeetingCardRevisions(MeetingUseCase):
    async def execute(
        self, actor: User, meeting_id: int, card_id: int
    ) -> list[MeetingCardRevisionResult]:
        meeting = await load_meeting(self._ports, meeting_id)
        card = await load_card(self._ports, meeting, card_id)
        revisions = await self._cards.get_revisions(card.id)
        users = await self._meetings.get_users({r.author_id for r in revisions})
        return [MeetingMapper.revision(revision, users) for revision in revisions]


class RestoreMeetingCardRevision(MeetingUseCase):
    """Saves an old revision's content as the card's newest revision."""

    async def execute(
        self,
        actor: User,
        meeting_id: int,
        card_id: int,
        revision_id: int,
        expected_edit_version: int,
    ) -> MeetingCardResult:
        meeting = await _writable(self._ports, actor, meeting_id)
        await self._cards.lock_card(card_id)
        card = await load_card(self._ports, meeting, card_id)
        assert_edit_version(card, expected_edit_version, what=f"Card #{card.id}")
        revision = await self._cards.get_revision(revision_id)
        if revision is None or revision.card_id != card.id:
            raise MeetingCardRevisionNotFoundError(f"Revision #{revision_id} not found.")
        saved = await save_card_content(
            self._ports,
            actor,
            card,
            scope=revision.scope,
            scope_icon=revision.scope_icon,
            body=revision.body,
            internal=revision.internal,
            always_new_revision=True,
        )
        await record(
            self._ports,
            meeting.id,
            MeetingEventKind.CARD_CHANGED,
            actor,
            card_id=card.id,
            summary=card_label(saved.card),
            details={"restored_revision_id": revision.id},
        )
        await self._uow.commit()
        return await card_result(self._ports, saved.card)


class AnnounceMeetingCardPresence(MeetingUseCase):
    """Tells the open meeting pages that the actor edits the card, or has
    stopped. The client repeats it every 20 seconds while editing."""

    def __init__(self, ports: MeetingPorts, presence: IMeetingPresence) -> None:
        super().__init__(ports)
        self._presence = presence

    async def execute(self, actor: User, meeting_id: int, card_id: int, editing: bool) -> None:
        meeting = await _writable(self._ports, actor, meeting_id)
        card = await load_card(self._ports, meeting, card_id)
        # Nothing is written, so the read transaction ends before the publish.
        await self._uow.commit()
        await self._presence.announce(card.id, actor.id, editing=editing)
