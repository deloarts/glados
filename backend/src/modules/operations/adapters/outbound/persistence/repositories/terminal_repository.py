"""
Concrete implementation of ITerminalRepository using SQLAlchemy.

The device details are split on write: the fields the terminals table shows
go to typed columns, the rest to the `device_details` JSON column. A read
puts them back together through the domain parser, so a hand-edited row
still comes back clean. The display schedule of the shown screen is read
with the screen, so the display power needs no second query.
"""

from datetime import datetime
from functools import lru_cache
from typing import Any

from sqlalchemy import and_
from sqlalchemy import delete
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.operations.adapters.outbound.persistence.models.terminal_model import (
    TerminalOrmModel,
)
from src.modules.operations.adapters.outbound.persistence.repositories.infoscreen_repository import (
    schedule_mode,
)
from src.modules.operations.domain.entities.terminal import Terminal
from src.modules.operations.domain.errors import InvalidInfoscreenConfigError
from src.modules.operations.domain.value_objects.display_schedule import DisplayPower
from src.modules.operations.domain.value_objects.display_schedule import DisplaySchedule
from src.modules.operations.domain.value_objects.display_schedule import DisplayScheduleMode
from src.modules.operations.domain.value_objects.display_schedule import parse_display_schedule
from src.modules.operations.domain.value_objects.terminal import TerminalMode
from src.modules.operations.domain.value_objects.terminal import TerminalStatus
from src.modules.operations.domain.value_objects.terminal_device_details import (
    TerminalDeviceDetails,
)
from src.modules.operations.domain.value_objects.terminal_device_details import (
    device_details_to_data,
)
from src.modules.operations.domain.value_objects.terminal_device_details import parse_device_details
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.adapters.outbound.persistence.user_loading import load_user
from src.modules.platform.adapters.outbound.persistence.user_loading import user_orm_to_entity
from src.modules.platform.infrastructure.logging.logger import log

_PENDING = TerminalStatus.PENDING.value

# Device detail fields kept in typed columns, by column name.
_TYPED_DETAIL_COLUMNS: dict[str, str] = {
    "computer_model": "device_computer_model",
    "ram_mb": "device_ram_mb",
    "os_name": "device_os_name",
    "display_make": "device_display_make",
    "display_model": "device_display_model",
    "display_width_px": "device_display_width_px",
    "display_height_px": "device_display_height_px",
}


@lru_cache(maxsize=1)
def _load_options() -> tuple[ORMOption, ...]:
    """Everything _orm_to_entity() dereferences. Built on first call, after
    every model module is registered."""
    return (
        selectinload(TerminalOrmModel.infoscreen),
        selectinload(TerminalOrmModel.api_key),
        load_user(TerminalOrmModel.approved_by),
    )


def _device(orm: TerminalOrmModel) -> TerminalDeviceDetails | None:
    if orm.device_reported_at is None:
        return None
    raw: dict[str, Any] = dict(orm.device_details) if isinstance(orm.device_details, dict) else {}
    for field_name, column in _TYPED_DETAIL_COLUMNS.items():
        raw[field_name] = getattr(orm, column)
    return parse_device_details(raw)


def _device_to_dict(details: TerminalDeviceDetails | None) -> dict[str, Any]:
    data = device_details_to_data(details) if details is not None else {}
    typed = {
        column: data.pop(field_name, None) for field_name, column in _TYPED_DETAIL_COLUMNS.items()
    }
    return {**typed, "device_details": data if details is not None else None}


def _screen_schedule(orm: TerminalOrmModel) -> DisplaySchedule | None:
    if orm.infoscreen is None:
        return None
    try:
        return parse_display_schedule(orm.infoscreen.display_schedule)
    except InvalidInfoscreenConfigError:
        log.warning(
            "Infoscreen #%s has a stored display schedule that no longer parses; "
            "treating it as always on.",
            orm.infoscreen.id,
        )
        return None


def _orm_to_entity(orm: TerminalOrmModel) -> Terminal:
    return Terminal(
        id=orm.id,
        public_id=orm.public_id,
        public_key=orm.public_key,
        public_key_fingerprint=orm.public_key_fingerprint,
        status=TerminalStatus(orm.status),
        mode=TerminalMode(orm.mode),
        name=orm.name,
        pairing_code=orm.pairing_code,
        pairing_expires_at=utc_aware(orm.pairing_expires_at),
        infoscreen_id=orm.infoscreen_id,
        api_key_id=orm.api_key_id,
        first_seen_at=utc_aware(orm.first_seen_at),
        last_seen_at=utc_aware(orm.last_seen_at),
        last_ip=orm.last_ip,
        user_agent=orm.user_agent,
        screen_width=orm.screen_width,
        screen_height=orm.screen_height,
        frontend_version=orm.frontend_version,
        bridge_version=orm.bridge_version,
        device=_device(orm),
        device_reported_at=utc_aware(orm.device_reported_at),
        location=orm.location,
        approved_at=utc_aware(orm.approved_at),
        approved_by_id=orm.approved_by_id,
        revoked_at=utc_aware(orm.revoked_at),
        reload_requested_at=utc_aware(orm.reload_requested_at),
        identify_requested_at=utc_aware(orm.identify_requested_at),
        display_override=(
            DisplayPower(orm.display_override) if orm.display_override is not None else None
        ),
        display_override_until=utc_aware(orm.display_override_until),
        last_session_at=utc_aware(orm.last_session_at),
        last_session_ip=orm.last_session_ip,
        duplicate_detected_at=utc_aware(orm.duplicate_detected_at),
        created=utc_aware(orm.created),
        changed=utc_aware(orm.changed),
        infoscreen_name=orm.infoscreen.name if orm.infoscreen else None,
        api_key_name=orm.api_key.name if orm.api_key else None,
        approved_by=user_orm_to_entity(orm.approved_by) if orm.approved_by else None,
        screen_display_schedule=_screen_schedule(orm),
        screen_off_on_holidays=bool(orm.infoscreen.off_on_holidays) if orm.infoscreen else False,
        screen_display_schedule_mode=(
            schedule_mode(orm.infoscreen.display_schedule_mode)
            if orm.infoscreen
            else DisplayScheduleMode.DEFAULT
        ),
    )


def _entity_to_dict(t: Terminal) -> dict[str, Any]:
    return {
        "public_key": t.public_key,
        "public_key_fingerprint": t.public_key_fingerprint,
        "status": t.status.value,
        "mode": t.mode.value,
        "name": t.name,
        "pairing_code": t.pairing_code,
        "pairing_expires_at": t.pairing_expires_at,
        "infoscreen_id": t.infoscreen_id,
        "api_key_id": t.api_key_id,
        "first_seen_at": t.first_seen_at,
        "last_seen_at": t.last_seen_at,
        "last_ip": t.last_ip,
        "user_agent": t.user_agent,
        "screen_width": t.screen_width,
        "screen_height": t.screen_height,
        "frontend_version": t.frontend_version,
        "bridge_version": t.bridge_version,
        **_device_to_dict(t.device),
        "device_reported_at": t.device_reported_at,
        "location": t.location,
        "approved_at": t.approved_at,
        "approved_by_id": t.approved_by_id,
        "revoked_at": t.revoked_at,
        "reload_requested_at": t.reload_requested_at,
        "identify_requested_at": t.identify_requested_at,
        "display_override": (t.display_override.value if t.display_override is not None else None),
        "display_override_until": t.display_override_until,
        "last_session_at": t.last_session_at,
        "last_session_ip": t.last_session_ip,
        "duplicate_detected_at": t.duplicate_detected_at,
        "created": t.created,
        "changed": t.changed,
    }


def _active_pending(now: datetime) -> Any:
    return and_(TerminalOrmModel.status == _PENDING, TerminalOrmModel.pairing_expires_at > now)


class SqlAlchemyTerminalRepository:
    """Implements ITerminalRepository."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, id: int) -> Terminal | None:
        orm = await self._db.scalar(by_id(TerminalOrmModel, id, *_load_options()).limit(1))
        return _orm_to_entity(orm) if orm else None

    async def lock_for_update(self, id: int) -> Terminal | None:
        orm = await self._db.scalar(
            by_id(TerminalOrmModel, id, *_load_options(), for_update=True, refresh=True).limit(1)
        )
        return _orm_to_entity(orm) if orm else None

    async def touch_seen(self, id: int, seen_at: datetime, ip: str | None) -> None:
        await self._db.execute(
            update(TerminalOrmModel)
            .where(TerminalOrmModel.id == id)
            .values(last_seen_at=seen_at, last_ip=ip)
        )

    async def get_by_public_key(self, public_key: str) -> Terminal | None:
        orm = await self._db.scalar(
            select(TerminalOrmModel)
            .where(TerminalOrmModel.public_key == public_key)
            .options(*_load_options())
            .limit(1)
        )
        return _orm_to_entity(orm) if orm else None

    async def get_visible(self, now: datetime) -> list[Terminal]:
        rows = await self._db.scalars(
            select(TerminalOrmModel)
            .where(or_(TerminalOrmModel.status != _PENDING, _active_pending(now)))
            .options(*_load_options())
            .order_by(TerminalOrmModel.id)
        )
        return [_orm_to_entity(r) for r in rows]

    async def get_all(self) -> list[Terminal]:
        rows = await self._db.scalars(
            select(TerminalOrmModel).options(*_load_options()).order_by(TerminalOrmModel.id)
        )
        return [_orm_to_entity(r) for r in rows]

    async def get_by_status(self, status: str) -> list[Terminal]:
        rows = await self._db.scalars(
            select(TerminalOrmModel)
            .where(TerminalOrmModel.status == status)
            .options(*_load_options())
            .order_by(TerminalOrmModel.id)
        )
        return [_orm_to_entity(r) for r in rows]

    async def count_active_pending(self, now: datetime) -> int:
        count = await self._db.scalar(
            select(func.count()).select_from(TerminalOrmModel).where(_active_pending(now))
        )
        return int(count or 0)

    async def get_pending_pairing_codes(self) -> set[str]:
        rows = await self._db.scalars(
            select(TerminalOrmModel.pairing_code).where(
                TerminalOrmModel.status == _PENDING, TerminalOrmModel.pairing_code.is_not(None)
            )
        )
        return {code for code in rows if code}

    async def delete_stale_pending(self, expired_before: datetime) -> int:
        stale = list(
            await self._db.scalars(
                select(TerminalOrmModel.id).where(
                    TerminalOrmModel.status == _PENDING,
                    TerminalOrmModel.pairing_expires_at < expired_before,
                )
            )
        )
        if stale:
            await self._db.execute(delete(TerminalOrmModel).where(TerminalOrmModel.id.in_(stale)))
        return len(stale)

    async def save(self, terminal: Terminal) -> Terminal:
        if terminal.id == 0:
            orm = TerminalOrmModel(**_entity_to_dict(terminal))
            self._db.add(orm)
            await self._db.flush()
            return _orm_to_entity(await self._reload(orm.id))
        existing = await self._db.scalar(by_id(TerminalOrmModel, terminal.id).limit(1))
        if existing is None:
            raise ValueError(f"TerminalOrmModel id={terminal.id} not found.")
        for key, value in _entity_to_dict(terminal).items():
            setattr(existing, key, value)
        await self._db.flush()
        return _orm_to_entity(await self._reload(terminal.id))

    async def delete(self, terminal: Terminal) -> None:
        existing = await self._db.scalar(by_id(TerminalOrmModel, terminal.id).limit(1))
        if existing is not None:
            await self._db.delete(existing)
            await self._db.flush()

    async def _reload(self, id: int) -> TerminalOrmModel:
        return (
            await self._db.scalars(by_id(TerminalOrmModel, id, *_load_options(), refresh=True))
        ).one()
