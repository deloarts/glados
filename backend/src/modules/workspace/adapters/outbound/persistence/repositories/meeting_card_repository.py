"""
Concrete implementation of IMeetingCardRepository using SQLAlchemy: the
cards of meetings with their revisions, mentions, decisions and todos, and
the scopes the cards use.
"""

from collections import Counter
from collections import defaultdict
from datetime import date
from functools import lru_cache
from typing import Any

from sqlalchemy import delete
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.base import ExecutableOption

from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.statements import lock_row
from src.modules.workspace.adapters.outbound.persistence.models.meeting_model import (
    MeetingCardMentionOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.meeting_model import (
    MeetingCardOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.meeting_model import (
    MeetingCardRevisionOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.meeting_model import (
    MeetingDecisionOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.meeting_model import (
    MeetingFileOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.meeting_model import MeetingOrmModel
from src.modules.workspace.adapters.outbound.persistence.models.meeting_model import (
    MeetingTodoOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.meeting_model import (
    MeetingTodoOwnerOrmModel,
)
from src.modules.workspace.domain.entities.meeting import MeetingCard
from src.modules.workspace.domain.entities.meeting import MeetingCardMention
from src.modules.workspace.domain.entities.meeting import MeetingCardRevision
from src.modules.workspace.domain.entities.meeting import MeetingDecision
from src.modules.workspace.domain.entities.meeting import MeetingTodo
from src.modules.workspace.domain.entities.meeting import MeetingTodoOwner
from src.modules.workspace.domain.services.meeting_scopes import ScopeUse
from src.modules.workspace.domain.value_objects.meeting import MeetingOwnerKind
from src.modules.workspace.domain.value_objects.meeting import MeetingScopeIcon
from src.modules.workspace.ports.outbound.workspace_queries import MeetingTodoRow


@lru_cache(maxsize=1)
def todo_load_options() -> tuple[ExecutableOption, ...]:
    return (selectinload(MeetingTodoOrmModel.owners),)


def _icon(value: str | None) -> MeetingScopeIcon | None:
    return MeetingScopeIcon(value) if value else None


def _card_to_entity(orm: MeetingCardOrmModel) -> MeetingCard:
    return MeetingCard(
        id=orm.id,
        public_id=orm.public_id,
        meeting_id=orm.meeting_id,
        position=orm.position,
        scope=orm.scope,
        scope_icon=_icon(orm.scope_icon),
        body=orm.body,
        internal=orm.internal,
        created=utc_aware(orm.created),
        creator_id=orm.creator_id,
        changed=utc_aware(orm.changed),
        changed_by_id=orm.changed_by_id,
        edit_version=orm.edit_version,
    )


def _card_columns(card: MeetingCard) -> dict[str, Any]:
    return {
        "meeting_id": card.meeting_id,
        "position": card.position,
        "scope": card.scope,
        "scope_icon": card.scope_icon.value if card.scope_icon else None,
        "body": card.body,
        "internal": card.internal,
        "created": card.created,
        "creator_id": card.creator_id,
        "changed": card.changed,
    }


def _revision_to_entity(orm: MeetingCardRevisionOrmModel) -> MeetingCardRevision:
    return MeetingCardRevision(
        id=orm.id,
        public_id=orm.public_id,
        card_id=orm.card_id,
        scope=orm.scope,
        scope_icon=_icon(orm.scope_icon),
        body=orm.body,
        internal=orm.internal,
        author_id=orm.author_id,
        created=utc_aware(orm.created),
        saved_at=utc_aware(orm.saved_at),
    )


def _mention_to_entity(orm: MeetingCardMentionOrmModel) -> MeetingCardMention:
    return MeetingCardMention(
        id=orm.id,
        public_id=orm.public_id,
        card_id=orm.card_id,
        user_id=orm.user_id,
        present=orm.present,
        created=utc_aware(orm.created),
    )


def _decision_to_entity(orm: MeetingDecisionOrmModel) -> MeetingDecision:
    return MeetingDecision(
        id=orm.id,
        public_id=orm.public_id,
        meeting_id=orm.meeting_id,
        card_id=orm.card_id,
        position=orm.position,
        text=orm.text,
        created=utc_aware(orm.created),
        creator_id=orm.creator_id,
    )


def _todo_to_entity(orm: MeetingTodoOrmModel) -> MeetingTodo:
    return MeetingTodo(
        id=orm.id,
        public_id=orm.public_id,
        meeting_id=orm.meeting_id,
        card_id=orm.card_id,
        position=orm.position,
        title=orm.title,
        created=utc_aware(orm.created),
        creator_id=orm.creator_id,
        note=orm.note,
        due_date=orm.due_date,
        done_at=utc_aware(orm.done_at),
        done_by_id=orm.done_by_id,
        changed=utc_aware(orm.changed),
        changed_by_id=orm.changed_by_id,
        owners=[
            MeetingTodoOwner(
                id=owner.id,
                public_id=owner.public_id,
                user_id=owner.user_id,
                contact_id=owner.contact_id,
                name=owner.name,
            )
            for owner in orm.owners
        ],
    )


def _todo_columns(todo: MeetingTodo) -> dict[str, Any]:
    return {
        "meeting_id": todo.meeting_id,
        "card_id": todo.card_id,
        "position": todo.position,
        "title": todo.title,
        "note": todo.note,
        "due_date": todo.due_date,
        "done_at": todo.done_at,
        "done_by_id": todo.done_by_id,
        "created": todo.created,
        "creator_id": todo.creator_id,
        "changed": todo.changed,
    }


class SqlAlchemyMeetingCardRepository:
    """Implements IMeetingCardRepository."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Cards ─────────────────────────────────────────────────────────

    async def get_cards(self, meeting_id: int) -> list[MeetingCard]:
        rows = await self._db.scalars(
            select(MeetingCardOrmModel)
            .where(MeetingCardOrmModel.meeting_id == meeting_id)
            .order_by(MeetingCardOrmModel.position, MeetingCardOrmModel.id)
        )
        return [_card_to_entity(row) for row in rows]

    async def get_card(self, card_id: int) -> MeetingCard | None:
        orm = await self._db.get(MeetingCardOrmModel, card_id, populate_existing=True)
        return _card_to_entity(orm) if orm is not None else None

    async def lock_card(self, card_id: int) -> None:
        await lock_row(self._db, MeetingCardOrmModel, card_id)

    async def save_card(self, card: MeetingCard) -> MeetingCard:
        if card.id == 0:
            orm = MeetingCardOrmModel(**_card_columns(card))
            self._db.add(orm)
        else:
            found = await self._db.get(MeetingCardOrmModel, card.id)
            if found is None:
                raise ValueError(f"MeetingCardOrmModel id={card.id} not found for update.")
            orm = found
            for key, value in _card_columns(card).items():
                setattr(orm, key, value)
        await self._db.flush()
        await self._db.refresh(orm)
        return _card_to_entity(orm)

    async def delete_card(self, card: MeetingCard) -> None:
        # Children first, so the delete does not depend on the database
        # enforcing its cascades.
        todos = select(MeetingTodoOrmModel.id).where(MeetingTodoOrmModel.card_id == card.id)
        for statement in (
            delete(MeetingTodoOwnerOrmModel).where(MeetingTodoOwnerOrmModel.todo_id.in_(todos)),
            delete(MeetingTodoOrmModel).where(MeetingTodoOrmModel.card_id == card.id),
            delete(MeetingDecisionOrmModel).where(MeetingDecisionOrmModel.card_id == card.id),
            delete(MeetingCardMentionOrmModel).where(MeetingCardMentionOrmModel.card_id == card.id),
            delete(MeetingCardRevisionOrmModel).where(
                MeetingCardRevisionOrmModel.card_id == card.id
            ),
            update(MeetingFileOrmModel)
            .where(MeetingFileOrmModel.card_id == card.id)
            .values(card_id=None),
        ):
            await self._db.execute(statement)
        orm = await self._db.get(MeetingCardOrmModel, card.id)
        if orm is not None:
            await self._db.delete(orm)
            await self._db.flush()

    async def set_positions(self, meeting_id: int, card_ids: list[int]) -> None:
        rows = await self._db.scalars(
            select(MeetingCardOrmModel).where(MeetingCardOrmModel.meeting_id == meeting_id)
        )
        by_id = {row.id: row for row in rows}
        for position, card_id in enumerate(card_ids):
            by_id[card_id].position = position
        await self._db.flush()

    async def next_position(self, meeting_id: int) -> int:
        highest = await self._db.scalar(
            select(func.max(MeetingCardOrmModel.position)).where(
                MeetingCardOrmModel.meeting_id == meeting_id
            )
        )
        return 0 if highest is None else int(highest) + 1

    async def get_cards_with_scope(self, meeting_ids: list[int], scope: str) -> list[MeetingCard]:
        if not meeting_ids:
            return []
        rows = await self._db.scalars(
            select(MeetingCardOrmModel).where(
                MeetingCardOrmModel.meeting_id.in_(meeting_ids), MeetingCardOrmModel.scope == scope
            )
        )
        return [_card_to_entity(row) for row in rows]

    async def get_scope_uses(self, meeting_ids: list[int]) -> list[ScopeUse]:
        if not meeting_ids:
            return []
        rows = await self._db.execute(
            select(MeetingCardOrmModel.scope, MeetingCardOrmModel.scope_icon).where(
                MeetingCardOrmModel.meeting_id.in_(meeting_ids),
                MeetingCardOrmModel.scope.is_not(None),
            )
        )
        counts: Counter[str] = Counter()
        icons: dict[str, Counter[str]] = defaultdict(Counter)
        for scope, icon in rows.all():
            counts[scope] += 1
            if icon:
                icons[scope][icon] += 1
        return [
            ScopeUse(
                scope=scope,
                count=count,
                icon=_icon(icons[scope].most_common(1)[0][0]) if icons[scope] else None,
            )
            for scope, count in counts.items()
        ]

    # ── Revisions and mentions ────────────────────────────────────────

    async def last_revision(self, card_id: int) -> MeetingCardRevision | None:
        orm = await self._db.scalar(
            select(MeetingCardRevisionOrmModel)
            .where(MeetingCardRevisionOrmModel.card_id == card_id)
            .order_by(MeetingCardRevisionOrmModel.id.desc())
            .limit(1)
        )
        return _revision_to_entity(orm) if orm is not None else None

    async def get_revisions(self, card_id: int) -> list[MeetingCardRevision]:
        rows = await self._db.scalars(
            select(MeetingCardRevisionOrmModel)
            .where(MeetingCardRevisionOrmModel.card_id == card_id)
            .order_by(MeetingCardRevisionOrmModel.id.desc())
        )
        return [_revision_to_entity(row) for row in rows]

    async def get_revision(self, revision_id: int) -> MeetingCardRevision | None:
        orm = await self._db.get(MeetingCardRevisionOrmModel, revision_id)
        return _revision_to_entity(orm) if orm is not None else None

    async def save_revision(self, revision: MeetingCardRevision) -> MeetingCardRevision:
        columns = {
            "card_id": revision.card_id,
            "scope": revision.scope,
            "scope_icon": revision.scope_icon.value if revision.scope_icon else None,
            "body": revision.body,
            "internal": revision.internal,
            "author_id": revision.author_id,
            "created": revision.created,
            "saved_at": revision.saved_at,
        }
        if revision.id == 0:
            orm = MeetingCardRevisionOrmModel(**columns)
            self._db.add(orm)
        else:
            found = await self._db.get(MeetingCardRevisionOrmModel, revision.id)
            if found is None:
                raise ValueError(f"MeetingCardRevisionOrmModel id={revision.id} not found.")
            orm = found
            for key, value in columns.items():
                setattr(orm, key, value)
        await self._db.flush()
        return _revision_to_entity(orm)

    async def get_mentions(self, card_id: int) -> list[MeetingCardMention]:
        rows = await self._db.scalars(
            select(MeetingCardMentionOrmModel).where(MeetingCardMentionOrmModel.card_id == card_id)
        )
        return [_mention_to_entity(row) for row in rows]

    async def save_mention(self, mention: MeetingCardMention) -> MeetingCardMention:
        if mention.id == 0:
            orm = MeetingCardMentionOrmModel(
                card_id=mention.card_id,
                user_id=mention.user_id,
                present=mention.present,
                created=mention.created,
            )
            self._db.add(orm)
        else:
            found = await self._db.get(MeetingCardMentionOrmModel, mention.id)
            if found is None:
                raise ValueError(f"MeetingCardMentionOrmModel id={mention.id} not found.")
            orm = found
            orm.present = mention.present
        await self._db.flush()
        return _mention_to_entity(orm)

    # ── Decisions ─────────────────────────────────────────────────────

    async def get_decisions(self, meeting_id: int) -> list[MeetingDecision]:
        rows = await self._db.scalars(
            select(MeetingDecisionOrmModel)
            .where(MeetingDecisionOrmModel.meeting_id == meeting_id)
            .order_by(
                MeetingDecisionOrmModel.card_id,
                MeetingDecisionOrmModel.position,
                MeetingDecisionOrmModel.id,
            )
        )
        return [_decision_to_entity(row) for row in rows]

    async def get_decision(self, decision_id: int) -> MeetingDecision | None:
        orm = await self._db.get(MeetingDecisionOrmModel, decision_id)
        return _decision_to_entity(orm) if orm is not None else None

    async def save_decision(self, decision: MeetingDecision) -> MeetingDecision:
        columns = {
            "meeting_id": decision.meeting_id,
            "card_id": decision.card_id,
            "position": decision.position,
            "text": decision.text,
            "created": decision.created,
            "creator_id": decision.creator_id,
        }
        if decision.id == 0:
            orm = MeetingDecisionOrmModel(**columns)
            self._db.add(orm)
        else:
            found = await self._db.get(MeetingDecisionOrmModel, decision.id)
            if found is None:
                raise ValueError(f"MeetingDecisionOrmModel id={decision.id} not found.")
            orm = found
            for key, value in columns.items():
                setattr(orm, key, value)
        await self._db.flush()
        return _decision_to_entity(orm)

    async def delete_decision(self, decision: MeetingDecision) -> None:
        orm = await self._db.get(MeetingDecisionOrmModel, decision.id)
        if orm is not None:
            await self._db.delete(orm)
            await self._db.flush()

    async def next_decision_position(self, card_id: int) -> int:
        highest = await self._db.scalar(
            select(func.max(MeetingDecisionOrmModel.position)).where(
                MeetingDecisionOrmModel.card_id == card_id
            )
        )
        return 0 if highest is None else int(highest) + 1

    # ── Todos ─────────────────────────────────────────────────────────

    async def _todo_orm(self, todo_id: int) -> MeetingTodoOrmModel | None:
        orm: MeetingTodoOrmModel | None = await self._db.scalar(
            select(MeetingTodoOrmModel)
            .where(MeetingTodoOrmModel.id == todo_id)
            .options(*todo_load_options())
            .execution_options(populate_existing=True)
        )
        return orm

    async def get_todos(self, meeting_id: int) -> list[MeetingTodo]:
        rows = await self._db.scalars(
            select(MeetingTodoOrmModel)
            .where(MeetingTodoOrmModel.meeting_id == meeting_id)
            .options(*todo_load_options())
            .order_by(
                MeetingTodoOrmModel.card_id, MeetingTodoOrmModel.position, MeetingTodoOrmModel.id
            )
        )
        return [_todo_to_entity(row) for row in rows]

    async def get_todo(self, todo_id: int) -> MeetingTodo | None:
        orm = await self._todo_orm(todo_id)
        return _todo_to_entity(orm) if orm is not None else None

    async def save_todo(self, todo: MeetingTodo) -> MeetingTodo:
        if todo.id == 0:
            orm = MeetingTodoOrmModel(**_todo_columns(todo))
            orm.owners = []
            self._db.add(orm)
        else:
            found = await self._todo_orm(todo.id)
            if found is None:
                raise ValueError(f"MeetingTodoOrmModel id={todo.id} not found for update.")
            orm = found
            for key, value in _todo_columns(todo).items():
                setattr(orm, key, value)
        wanted = {(owner.user_id, owner.contact_id): owner for owner in todo.owners}
        kept = [row for row in orm.owners if (row.user_id, row.contact_id) in wanted]
        for row in kept:
            row.name = wanted[(row.user_id, row.contact_id)].name
        present = {(row.user_id, row.contact_id) for row in kept}
        added = [
            MeetingTodoOwnerOrmModel(
                user_id=owner.user_id, contact_id=owner.contact_id, name=owner.name
            )
            for key, owner in wanted.items()
            if key not in present
        ]
        orm.owners = kept + added
        await self._db.flush()
        reloaded = await self._todo_orm(orm.id)
        assert reloaded is not None
        return _todo_to_entity(reloaded)

    async def delete_todo(self, todo: MeetingTodo) -> None:
        orm = await self._todo_orm(todo.id)
        if orm is not None:
            await self._db.delete(orm)
            await self._db.flush()

    async def next_todo_position(self, card_id: int) -> int:
        highest = await self._db.scalar(
            select(func.max(MeetingTodoOrmModel.position)).where(
                MeetingTodoOrmModel.card_id == card_id
            )
        )
        return 0 if highest is None else int(highest) + 1

    async def get_open_todos(self, meeting_ids: list[int]) -> list[MeetingTodo]:
        if not meeting_ids:
            return []
        rows = await self._db.scalars(
            select(MeetingTodoOrmModel)
            .where(
                MeetingTodoOrmModel.meeting_id.in_(meeting_ids),
                MeetingTodoOrmModel.done_at.is_(None),
            )
            .options(*todo_load_options())
            .order_by(MeetingTodoOrmModel.meeting_id, MeetingTodoOrmModel.position)
        )
        return [_todo_to_entity(row) for row in rows]

    async def list_open_todos_of_user(
        self, user_id: int, *, due_on_or_before: date
    ) -> list[MeetingTodoRow]:
        owned = select(MeetingTodoOwnerOrmModel.todo_id).where(
            MeetingTodoOwnerOrmModel.user_id == user_id
        )
        result = await self._db.execute(
            select(
                MeetingTodoOrmModel.id,
                MeetingTodoOrmModel.title,
                MeetingTodoOrmModel.due_date,
                MeetingOrmModel.id,
                MeetingOrmModel.meeting_number,
                MeetingOrmModel.name,
                MeetingOrmModel.project_id,
                MeetingOrmModel.product_id,
                MeetingCardOrmModel.id,
                MeetingCardOrmModel.scope,
            )
            .join(MeetingOrmModel, MeetingOrmModel.id == MeetingTodoOrmModel.meeting_id)
            .join(MeetingCardOrmModel, MeetingCardOrmModel.id == MeetingTodoOrmModel.card_id)
            .where(
                MeetingTodoOrmModel.id.in_(owned),
                MeetingTodoOrmModel.done_at.is_(None),
                MeetingOrmModel.deleted.is_(False),
                MeetingOrmModel.invalid_at.is_(None),
                or_(
                    MeetingTodoOrmModel.due_date.is_(None),
                    MeetingTodoOrmModel.due_date <= due_on_or_before,
                ),
            )
            .order_by(
                MeetingTodoOrmModel.due_date.is_(None),
                MeetingTodoOrmModel.due_date,
                MeetingOrmModel.starts_at,
                MeetingCardOrmModel.position,
                MeetingTodoOrmModel.position,
                MeetingTodoOrmModel.id,
            )
        )
        rows: list[MeetingTodoRow] = []
        for (
            todo_id,
            title,
            due_date,
            meeting_id,
            number,
            name,
            project_id,
            product_id,
            card_id,
            scope,
        ) in result.all():
            owner_kind = (
                MeetingOwnerKind.PROJECT if project_id is not None else MeetingOwnerKind.PRODUCT
            )
            rows.append(
                MeetingTodoRow(
                    todo_id=todo_id,
                    title=title,
                    due_date=due_date,
                    meeting_id=meeting_id,
                    meeting_number=number,
                    meeting_name=name,
                    owner_kind=owner_kind,
                    owner_id=project_id if project_id is not None else product_id,
                    card_id=card_id,
                    card_scope=scope,
                )
            )
        return rows
