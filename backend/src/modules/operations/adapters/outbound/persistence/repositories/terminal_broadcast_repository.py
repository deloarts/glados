"""
Concrete implementation of ITerminalBroadcastRepository using SQLAlchemy.
The picks of a message are read from the two link tables in one query
each for every message of a read.
"""

from collections.abc import Sequence
from datetime import datetime
from functools import lru_cache
from typing import Any

from sqlalchemy import insert
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.operations.adapters.outbound.persistence.models.terminal_broadcast_model import (
    TerminalBroadcastOrmModel,
)
from src.modules.operations.adapters.outbound.persistence.models.terminal_broadcast_model import (
    terminal_broadcast_infoscreen_table,
)
from src.modules.operations.adapters.outbound.persistence.models.terminal_broadcast_model import (
    terminal_broadcast_terminal_table,
)
from src.modules.operations.domain.entities.terminal_broadcast import TerminalBroadcast
from src.modules.operations.domain.value_objects.terminal_broadcast import TerminalBroadcastSeverity
from src.modules.operations.domain.value_objects.terminal_broadcast import TerminalBroadcastStyle
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.adapters.outbound.persistence.user_loading import load_user
from src.modules.platform.adapters.outbound.persistence.user_loading import user_orm_to_entity

_TERMINAL_LINKS = terminal_broadcast_terminal_table
_SCREEN_LINKS = terminal_broadcast_infoscreen_table


@lru_cache(maxsize=1)
def _load_options() -> tuple[ORMOption, ...]:
    """Everything _orm_to_entity() dereferences."""
    return (load_user(TerminalBroadcastOrmModel.created_by),)


def _orm_to_entity(
    orm: TerminalBroadcastOrmModel, terminal_ids: list[int], infoscreen_ids: list[int]
) -> TerminalBroadcast:
    return TerminalBroadcast(
        id=orm.id,
        public_id=orm.public_id,
        created=utc_aware(orm.created),
        changed=utc_aware(orm.changed),
        text=orm.text,
        severity=TerminalBroadcastSeverity(orm.severity),
        style=TerminalBroadcastStyle(orm.style),
        show_until=utc_aware(orm.show_until),
        all_terminals=orm.all_terminals,
        ended_at=utc_aware(orm.ended_at),
        created_by_id=orm.created_by_id,
        terminal_ids=tuple(sorted(terminal_ids)),
        infoscreen_ids=tuple(sorted(infoscreen_ids)),
        created_by=user_orm_to_entity(orm.created_by) if orm.created_by else None,
    )


def _entity_to_dict(b: TerminalBroadcast) -> dict[str, Any]:
    return {
        "created": b.created,
        "changed": b.changed,
        "text": b.text,
        "severity": b.severity.value,
        "style": b.style.value,
        "show_until": b.show_until,
        "all_terminals": b.all_terminals,
        "ended_at": b.ended_at,
        "created_by_id": b.created_by_id,
    }


class SqlAlchemyTerminalBroadcastRepository:
    """Implements ITerminalBroadcastRepository."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, id: int) -> TerminalBroadcast | None:
        orm = await self._db.scalar(by_id(TerminalBroadcastOrmModel, id, *_load_options()).limit(1))
        return (await self._with_picks([orm]))[0] if orm else None

    async def get_active(self, now: datetime) -> list[TerminalBroadcast]:
        rows = await self._db.scalars(
            select(TerminalBroadcastOrmModel)
            .where(
                TerminalBroadcastOrmModel.ended_at.is_(None),
                TerminalBroadcastOrmModel.show_until > now,
            )
            .options(*_load_options())
            .order_by(TerminalBroadcastOrmModel.created.desc(), TerminalBroadcastOrmModel.id.desc())
        )
        return await self._with_picks(list(rows))

    async def save(self, broadcast: TerminalBroadcast) -> TerminalBroadcast:
        if broadcast.id == 0:
            orm = TerminalBroadcastOrmModel(**_entity_to_dict(broadcast))
            self._db.add(orm)
            await self._db.flush()
            if broadcast.terminal_ids:
                await self._db.execute(
                    insert(_TERMINAL_LINKS),
                    [{"broadcast_id": orm.id, "terminal_id": i} for i in broadcast.terminal_ids],
                )
            if broadcast.infoscreen_ids:
                await self._db.execute(
                    insert(_SCREEN_LINKS),
                    [
                        {"broadcast_id": orm.id, "infoscreen_id": i}
                        for i in broadcast.infoscreen_ids
                    ],
                )
            return await self._reload(orm.id)
        existing = await self._db.scalar(by_id(TerminalBroadcastOrmModel, broadcast.id).limit(1))
        if existing is None:
            raise ValueError(f"TerminalBroadcastOrmModel id={broadcast.id} not found.")
        existing.changed = broadcast.changed
        existing.ended_at = broadcast.ended_at
        await self._db.flush()
        return await self._reload(broadcast.id)

    async def _reload(self, id: int) -> TerminalBroadcast:
        orm = (
            await self._db.scalars(
                by_id(TerminalBroadcastOrmModel, id, *_load_options(), refresh=True)
            )
        ).one()
        return (await self._with_picks([orm]))[0]

    async def _with_picks(
        self, rows: Sequence[TerminalBroadcastOrmModel]
    ) -> list[TerminalBroadcast]:
        ids = [r.id for r in rows]
        terminals: dict[int, list[int]] = {}
        screens: dict[int, list[int]] = {}
        if ids:
            for broadcast_id, terminal_id in await self._db.execute(
                select(_TERMINAL_LINKS.c.broadcast_id, _TERMINAL_LINKS.c.terminal_id).where(
                    _TERMINAL_LINKS.c.broadcast_id.in_(ids)
                )
            ):
                terminals.setdefault(broadcast_id, []).append(terminal_id)
            for broadcast_id, infoscreen_id in await self._db.execute(
                select(_SCREEN_LINKS.c.broadcast_id, _SCREEN_LINKS.c.infoscreen_id).where(
                    _SCREEN_LINKS.c.broadcast_id.in_(ids)
                )
            ):
                screens.setdefault(broadcast_id, []).append(infoscreen_id)
        return [_orm_to_entity(r, terminals.get(r.id, []), screens.get(r.id, [])) for r in rows]
