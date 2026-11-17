"""
The decisions and todos of a meeting's cards. A todo has a title, an
optional note and due date and owners, users or contacts; assigning a user
queues their notification. Writing needs write:meetings and a meeting that
is not invalid; ticking a todo off or reopening it is open to its owners
too.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.workspace.application.dto.meeting_dto import MeetingDecisionCommand
from src.modules.workspace.application.dto.meeting_dto import MeetingDecisionResult
from src.modules.workspace.application.dto.meeting_dto import MeetingTodoCommand
from src.modules.workspace.application.dto.meeting_dto import MeetingTodoResult
from src.modules.workspace.application.mappers.meeting_mapper import MeetingMapper
from src.modules.workspace.application.mappers.meeting_mapper import card_user_ids
from src.modules.workspace.application.use_cases.meeting._support import MeetingPorts
from src.modules.workspace.application.use_cases.meeting._support import MeetingUseCase
from src.modules.workspace.application.use_cases.meeting._support import load_card
from src.modules.workspace.application.use_cases.meeting._support import load_decision
from src.modules.workspace.application.use_cases.meeting._support import load_meeting
from src.modules.workspace.application.use_cases.meeting._support import load_todo
from src.modules.workspace.application.use_cases.meeting._support import queue_notifications
from src.modules.workspace.application.use_cases.meeting._support import record
from src.modules.workspace.application.use_cases.meeting._support import resolve_todo_owners
from src.modules.workspace.domain.entities.meeting import Meeting
from src.modules.workspace.domain.entities.meeting import MeetingDecision
from src.modules.workspace.domain.entities.meeting import MeetingTodo
from src.modules.workspace.domain.services.meeting_rules import DECISION_MAX
from src.modules.workspace.domain.services.meeting_rules import TODO_NOTE_MAX
from src.modules.workspace.domain.services.meeting_rules import TODO_TITLE_MAX
from src.modules.workspace.domain.services.meeting_rules import MeetingRules
from src.modules.workspace.domain.value_objects.meeting import MeetingEventKind
from src.shared_kernel.domain.services.clock import now_utc


async def _writable(ports: MeetingPorts, actor: User, meeting_id: int) -> Meeting:
    MeetingRules.assert_can_write(actor)
    meeting = await load_meeting(ports, meeting_id)
    MeetingRules.assert_editable(meeting)
    return meeting


async def _decision_result(ports: MeetingPorts, decision: MeetingDecision) -> MeetingDecisionResult:
    users = await ports.meetings.get_users({decision.creator_id})
    return MeetingMapper.decision(decision, users)


async def _todo_result(ports: MeetingPorts, todo: MeetingTodo) -> MeetingTodoResult:
    users = await ports.meetings.get_users(card_user_ids([], [], [todo]))
    return MeetingMapper.todo(todo, users)


# ── Decisions ─────────────────────────────────────────────────────────


class CreateMeetingDecision(MeetingUseCase):
    async def execute(
        self, actor: User, meeting_id: int, card_id: int, cmd: MeetingDecisionCommand
    ) -> MeetingDecisionResult:
        meeting = await _writable(self._ports, actor, meeting_id)
        card = await load_card(self._ports, meeting, card_id)
        decision = await self._cards.save_decision(
            MeetingDecision(
                id=0,
                meeting_id=meeting.id,
                card_id=card.id,
                position=await self._cards.next_decision_position(card.id),
                text=MeetingRules.required_text(cmd.text, "decision", DECISION_MAX),
                created=now_utc(),
                creator_id=actor.id,
            )
        )
        await self._uow.commit()
        return await _decision_result(self._ports, decision)


class UpdateMeetingDecision(MeetingUseCase):
    async def execute(
        self, actor: User, meeting_id: int, decision_id: int, cmd: MeetingDecisionCommand
    ) -> MeetingDecisionResult:
        meeting = await _writable(self._ports, actor, meeting_id)
        decision = await load_decision(self._ports, meeting, decision_id)
        decision.text = MeetingRules.required_text(cmd.text, "decision", DECISION_MAX)
        if cmd.position is not None:
            decision.position = max(cmd.position, 0)
        saved = await self._cards.save_decision(decision)
        await self._uow.commit()
        return await _decision_result(self._ports, saved)


class DeleteMeetingDecision(MeetingUseCase):
    async def execute(self, actor: User, meeting_id: int, decision_id: int) -> None:
        meeting = await _writable(self._ports, actor, meeting_id)
        decision = await load_decision(self._ports, meeting, decision_id)
        await self._cards.delete_decision(decision)
        await self._uow.commit()


# ── Todos ─────────────────────────────────────────────────────────────


def _apply_todo(todo: MeetingTodo, cmd: MeetingTodoCommand) -> None:
    todo.title = MeetingRules.required_text(cmd.title, "todo's title", TODO_TITLE_MAX)
    todo.note = MeetingRules.optional_text(cmd.note, "todo's note", TODO_NOTE_MAX)
    todo.due_date = cmd.due_date


class CreateMeetingTodo(MeetingUseCase):
    async def execute(
        self, actor: User, meeting_id: int, card_id: int, cmd: MeetingTodoCommand
    ) -> MeetingTodoResult:
        meeting = await _writable(self._ports, actor, meeting_id)
        card = await load_card(self._ports, meeting, card_id)
        todo = MeetingTodo(
            id=0,
            meeting_id=meeting.id,
            card_id=card.id,
            position=await self._cards.next_todo_position(card.id),
            title="",
            created=now_utc(),
            creator_id=actor.id,
        )
        _apply_todo(todo, cmd)
        todo.owners = await resolve_todo_owners(self._ports, cmd.owners, [])
        saved = await self._cards.save_todo(todo)
        await record(
            self._ports,
            meeting.id,
            MeetingEventKind.TODO_ADDED,
            actor,
            card_id=card.id,
            todo_id=saved.id,
            summary=saved.title,
        )
        await queue_notifications(
            self._ports, meeting.id, actor, todos={u: 1 for u in saved.owner_user_ids}
        )
        await self._uow.commit()
        return await _todo_result(self._ports, saved)


class UpdateMeetingTodo(MeetingUseCase):
    """Saves the todo's title, note, due date and owners. A user who becomes
    an owner is notified."""

    async def execute(
        self, actor: User, meeting_id: int, todo_id: int, cmd: MeetingTodoCommand
    ) -> MeetingTodoResult:
        meeting = await _writable(self._ports, actor, meeting_id)
        todo = await load_todo(self._ports, meeting, todo_id)
        before = todo.owner_user_ids
        _apply_todo(todo, cmd)
        todo.owners = await resolve_todo_owners(self._ports, cmd.owners, todo.owners)
        todo.changed = now_utc()
        saved = await self._cards.save_todo(todo)
        await queue_notifications(
            self._ports,
            meeting.id,
            actor,
            todos={u: 1 for u in saved.owner_user_ids - before},
        )
        await self._uow.commit()
        return await _todo_result(self._ports, saved)


class DeleteMeetingTodo(MeetingUseCase):
    async def execute(self, actor: User, meeting_id: int, todo_id: int) -> None:
        meeting = await _writable(self._ports, actor, meeting_id)
        todo = await load_todo(self._ports, meeting, todo_id)
        await self._cards.delete_todo(todo)
        await self._uow.commit()


class SetMeetingTodoDone(MeetingUseCase):
    """Ticks a todo off for everyone, or reopens it. Doing what is done
    already changes nothing."""

    async def execute(
        self, actor: User, meeting_id: int, todo_id: int, done: bool
    ) -> MeetingTodoResult:
        meeting = await load_meeting(self._ports, meeting_id)
        todo = await load_todo(self._ports, meeting, todo_id)
        MeetingRules.assert_can_tick(actor, todo)
        MeetingRules.assert_editable(meeting)
        if todo.done == done:
            return await _todo_result(self._ports, todo)
        now = now_utc()
        todo.done_at, todo.done_by_id = (now, actor.id) if done else (None, None)
        todo.changed = now
        saved = await self._cards.save_todo(todo)
        await record(
            self._ports,
            meeting.id,
            MeetingEventKind.TODO_DONE if done else MeetingEventKind.TODO_REOPENED,
            actor,
            at=now,
            card_id=todo.card_id,
            todo_id=todo.id,
            summary=todo.title,
        )
        await self._uow.commit()
        return await _todo_result(self._ports, saved)
