"""
HTTP-level coverage of /api/v1/web/notifications. Notifications are
produced by the system (event handlers), not created by a user via HTTP,
so there is no create route on this router:
every test seeds a Notification directly through the real repository (`db`
fixture) against a specific user id, then exercises the read/mark-read/
delete routes as that user via HTTP.

Every operation is scoped to the current user rather than gated by a
Permission constant, so the 403 case here is "acting on someone else's
notification" (InsufficientPermissionsError from mark_notification_read /
delete_notification), not a missing grant. `auth_client` doesn't expose the
persisted user's id, so tests use `create_user` + `auth_headers` directly
(the same pattern as test_api_auth.py) to know which user id to seed
notifications against.
"""

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.outbound.persistence.repositories.notification_repository import (
    SqlAlchemyNotificationRepository,
)
from src.modules.platform.domain.entities.notification import make_notification
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.notification_type import NotificationType

from .conftest import auth_headers


async def _seed(db: AsyncSession, user_id: int, **overrides: object) -> int:
    notification = make_notification(
        user_id=user_id,
        type=NotificationType.PERMISSIONS_CHANGED,
        title="Permissions changed",
        message="Your permissions were updated.",
    )
    for key, value in overrides.items():
        setattr(notification, key, value)
    saved = await SqlAlchemyNotificationRepository(db).save(notification)
    await db.commit()
    return saved.id


async def _as(client: httpx.AsyncClient, user: User) -> httpx.AsyncClient:
    client.headers.update(await auth_headers(user))
    return client


async def test_list_notifications_returns_only_own(client, create_user, db: AsyncSession) -> None:
    mine: User = await create_user(username="mine", email="mine@example.com")
    other: User = await create_user(username="other", email="other@example.com")
    await _seed(db, user_id=mine.id, title="Mine")
    await _seed(db, user_id=other.id, title="Not mine")

    resp = await (await _as(client, mine)).get("/api/v1/web/notifications/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["unread_count"] == 1
    assert body["items"][0]["title"] == "Mine"


async def test_list_notifications_unread_only(client, create_user, db: AsyncSession) -> None:
    user: User = await create_user()
    unread_id = await _seed(db, user_id=user.id, title="Unread")
    await _seed(db, user_id=user.id, title="Read", is_read=True)

    resp = await (await _as(client, user)).get(
        "/api/v1/web/notifications/", params={"unread_only": True}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == unread_id


async def test_mark_notification_read(client, create_user, db: AsyncSession) -> None:
    user: User = await create_user()
    notification_id = await _seed(db, user_id=user.id)

    resp = await (await _as(client, user)).patch(
        f"/api/v1/web/notifications/{notification_id}/read"
    )
    assert resp.status_code == 204

    listed = (await client.get("/api/v1/web/notifications/")).json()
    assert listed["unread_count"] == 0
    assert listed["items"][0]["is_read"] is True


async def test_mark_missing_notification_404(client, create_user) -> None:
    user: User = await create_user()
    resp = await (await _as(client, user)).patch("/api/v1/web/notifications/999999/read")
    assert resp.status_code == 404


async def test_mark_notification_read_rejects_non_integer_id(client, create_user) -> None:
    user: User = await create_user()
    resp = await (await _as(client, user)).patch("/api/v1/web/notifications/not-an-id/read")
    assert resp.status_code == 422


async def test_mark_read_of_other_users_notification_forbidden(
    client, create_user, db: AsyncSession
) -> None:
    owner: User = await create_user(username="owner", email="owner@example.com")
    intruder: User = await create_user(username="intruder", email="intruder@example.com")
    notification_id = await _seed(db, user_id=owner.id)

    resp = await (await _as(client, intruder)).patch(
        f"/api/v1/web/notifications/{notification_id}/read"
    )
    assert resp.status_code == 403


async def test_delete_notification(client, create_user, db: AsyncSession) -> None:
    user: User = await create_user()
    notification_id = await _seed(db, user_id=user.id)

    resp = await (await _as(client, user)).delete(f"/api/v1/web/notifications/{notification_id}")
    assert resp.status_code == 204

    listed = (await client.get("/api/v1/web/notifications/")).json()
    assert listed["total"] == 0


async def test_mark_all_notifications_read(client, create_user, db: AsyncSession) -> None:
    user: User = await create_user()
    await _seed(db, user_id=user.id, title="One")
    await _seed(db, user_id=user.id, title="Two")

    resp = await (await _as(client, user)).patch("/api/v1/web/notifications/read-all")
    assert resp.status_code == 204

    listed = (await client.get("/api/v1/web/notifications/")).json()
    assert listed["unread_count"] == 0


async def test_clear_all_notifications(client, create_user, db: AsyncSession) -> None:
    """This router's distinguishing feature beyond single-row CRUD: a bulk
    delete scoped to the current user, leaving other users' rows alone."""
    mine: User = await create_user(username="mine", email="mine@example.com")
    other: User = await create_user(username="other", email="other@example.com")
    await _seed(db, user_id=mine.id)
    await _seed(db, user_id=other.id)

    resp = await (await _as(client, mine)).delete("/api/v1/web/notifications/")
    assert resp.status_code == 204

    mine_listed = (await client.get("/api/v1/web/notifications/")).json()
    assert mine_listed["total"] == 0

    other_listed = (await (await _as(client, other)).get("/api/v1/web/notifications/")).json()
    assert other_listed["total"] == 1
