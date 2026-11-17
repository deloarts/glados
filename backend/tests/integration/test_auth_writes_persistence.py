"""
Proves that the session, trusted device and force-logout writes persist
what they report. Each write is read back from a fresh database session,
so a use case or dependency that forgets to commit its unit of work fails
here instead of silently losing a revocation. The last-seen stamp is
checked on a request that fails, because the sliding idle window must
advance whether or not the route itself succeeds.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy import update

from src.modules.platform.adapters.outbound.persistence.models.pat_model import PatOrmModel
from src.modules.platform.adapters.outbound.persistence.models.user_session_model import (
    UserSessionOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.user_trusted_device_model import (
    UserTrustedDeviceOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.repositories.pat_repository import (
    SqlAlchemyPatRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.trusted_device_repository import (
    SqlAlchemyTrustedDeviceRepository,
)
from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
from src.modules.platform.domain.entities.personal_access_token import PersonalAccessToken
from src.modules.platform.domain.entities.trusted_device import make_trusted_device
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission

from .conftest import _new_client
from .conftest import auth_headers

WEB = "/api/v1/web"


async def _seed_device(db: Any, user: User) -> None:
    await SqlAlchemyTrustedDeviceRepository(db).save(
        make_trusted_device(
            user_id=user.id, token_hash=uuid4().hex, trust_days=30, user_agent="pytest"
        )
    )
    await db.commit()


async def _seed_pat(db: Any, user: User) -> None:
    await SqlAlchemyPatRepository(db).save(
        PersonalAccessToken(
            id=0,
            name="seeded",
            token_hash=uuid4().hex,
            token_prefix="glados_pat_x",
            user_id=user.id,
            permissions=[],
            created=datetime.now(UTC),
            expires_at=None,
        )
    )
    await db.commit()


async def _live_rows(model: Any, user_id: int) -> int:
    async with SessionLocal() as fresh:
        rows = (
            await fresh.scalars(
                select(model).where(model.user_id == user_id, model.revoked_at.is_(None))
            )
        ).all()
        return len(rows)


async def test_revoking_all_my_trusted_devices_is_persisted(db, create_user) -> None:
    user = await create_user()
    await _seed_device(db, user)
    await _seed_device(db, user)

    async with _new_client() as client:
        client.headers.update(await auth_headers(user))
        response = await client.delete(f"{WEB}/users/me/trusted-devices/")

    assert response.status_code == 200, response.text
    assert response.json()["revoked"] == 2
    assert await _live_rows(UserTrustedDeviceOrmModel, user.id) == 0


async def test_force_logout_of_all_users_is_persisted(db, create_user) -> None:
    admin = await create_user("admin", "admin@example.com", [Permission.WRITE_SETTINGS])
    other = await create_user("other", "other@example.com")
    other_headers = await auth_headers(other)
    await _seed_device(db, other)
    await _seed_pat(db, other)

    async with _new_client() as client:
        client.headers.update(await auth_headers(admin))
        response = await client.delete(f"{WEB}/users/sessions")
    assert response.status_code == 200, response.text

    assert await _live_rows(UserSessionOrmModel, other.id) == 0
    assert await _live_rows(UserTrustedDeviceOrmModel, other.id) == 0
    assert await _live_rows(PatOrmModel, other.id) == 0
    async with _new_client() as client:
        client.headers.update(other_headers)
        assert (await client.get(f"{WEB}/users/me")).status_code == 401


async def test_last_seen_stamp_survives_a_failing_request(db, create_user) -> None:
    user = await create_user()
    headers = await auth_headers(user)
    stale = datetime.now(UTC) - timedelta(minutes=10)
    await db.execute(
        update(UserSessionOrmModel)
        .where(UserSessionOrmModel.user_id == user.id)
        .values(last_seen_at=stale)
    )
    await db.commit()

    async with _new_client() as client:
        client.headers.update(headers)
        response = await client.delete(f"{WEB}/users/me/sessions/{uuid4()}")
    assert response.status_code == 404, response.text

    async with SessionLocal() as fresh:
        last_seen = await fresh.scalar(
            select(UserSessionOrmModel.last_seen_at).where(UserSessionOrmModel.user_id == user.id)
        )
    assert last_seen is not None
    assert last_seen.replace(tzinfo=UTC) > stale + timedelta(minutes=5)
