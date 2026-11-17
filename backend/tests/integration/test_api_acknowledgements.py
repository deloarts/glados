"""
HTTP-level coverage of /api/v1/web/admin/acknowledgements (admin CRUD,
read:settings/write:settings) and /api/v1/web/announcements (any active
user). Mirrors test_api_webhooks.py's shape for the admin CRUD half.

The next_login gating test backdates session rows directly in the DB
rather than racing the wall clock between two rapid API calls, the same
idiom as test_api_session_timeout.py ("there is no clock to freeze when
the token itself never expires").
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.outbound.persistence.models.acknowledgement_model import (
    AcknowledgementOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.acknowledgement_model import (
    AcknowledgementRecipientOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.user_session_repository import (
    SqlAlchemyUserSessionRepository,
)
from src.modules.platform.adapters.outbound.persistence.statements import count_rows
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.entities.user_session import make_user_session
from src.modules.platform.infrastructure.security.token import create_access_token
from tests.integration.conftest import _new_client
from tests.integration.conftest import auth_headers

ADMIN_BASE = "/api/v1/web/admin/acknowledgements"
ANNOUNCEMENTS_BASE = "/api/v1/web/announcements"


async def auth_client_as(user: User) -> httpx.AsyncClient:
    """A client authenticated as an already-created user. Unlike the
    auth_client fixture (which always creates a fresh user), the
    recipient/non-recipient distinction in these tests needs specific,
    already-known users."""
    client = _new_client()
    client.headers.update(await auth_headers(user))
    return client


async def _headers_at(db: AsyncSession, user: User, created_at: datetime) -> dict[str, str]:
    """Same as tests.integration.conftest.auth_headers, but lets the
    caller pin the session row's created_at. The next_login gating tests
    need two sessions in a known before/after relationship, not whatever
    order the wall clock happens to give two rapid-fire calls."""
    session = make_user_session(user_id=user.id, user_agent="pytest", ip="testclient")
    session.created_at = created_at
    session.last_seen_at = created_at
    saved = await SqlAlchemyUserSessionRepository(db).save(session)
    await db.commit()
    token = create_access_token(
        subject=user.id,
        persistent=False,
        expires_delta=None,
        token_version=user.token_version,
        sid=str(saved.public_id),
    )
    return {"Authorization": f"Bearer {token}"}


async def _client_at(db: AsyncSession, user: User, created_at: datetime) -> httpx.AsyncClient:
    client = _new_client()
    client.headers.update(await _headers_at(db, user, created_at))
    return client


async def _rename(db: AsyncSession, user: User, full_name: str) -> User:
    user.full_name = full_name
    saved = await SqlAlchemyUserRepository(db).save(user)
    await db.commit()
    return saved


async def _mark_shared(db: AsyncSession, user: User) -> User:
    user.is_shared_account = True
    saved = await SqlAlchemyUserRepository(db).save(user)
    await db.commit()
    return saved


async def _create(client: httpx.AsyncClient, **overrides: object) -> dict:
    body = {
        "text": "Please confirm you have read the new safety policy.",
        "severity": "warning",
        "enabled": True,
        "show_when": "immediately",
    } | overrides
    resp = await client.post(f"{ADMIN_BASE}/", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Admin CRUD ────────────────────────────────────────────────────────


async def test_list_requires_read_settings(auth_client) -> None:
    client = await auth_client(permissions=[])
    resp = await client.get(f"{ADMIN_BASE}/")
    assert resp.status_code == 403


async def test_create_requires_write_settings(auth_client) -> None:
    client = await auth_client(permissions=["read:settings"])
    resp = await client.post(
        f"{ADMIN_BASE}/",
        json={
            "text": "x",
            "severity": "info",
            "enabled": True,
            "show_when": "immediately",
            "recipient_ids": [1],
        },
    )
    assert resp.status_code == 403


async def test_create_with_recipients_including_a_shared_account(
    auth_client, create_user, db
) -> None:
    admin = await auth_client(permissions=["write:settings", "read:settings"])
    normal = await create_user(username="alice", email="alice@example.com")
    shared = await _mark_shared(
        db, await create_user(username="shared-acct", email="shared@example.com")
    )

    created = await _create(admin, recipient_ids=[normal.id, shared.id])
    assert created["recipients_total"] == 2
    assert created["recipients_acknowledged"] == 0
    assert created["severity"] == "warning"
    assert created["show_when"] == "immediately"
    assert created["created_by_username"] is not None

    recipients = (await admin.get(f"{ADMIN_BASE}/{created['public_id']}/recipients")).json()
    assert {r["user_id"] for r in recipients} == {normal.id, shared.id}


async def test_create_rejects_empty_recipients(auth_client) -> None:
    client = await auth_client(permissions=["write:settings"])
    resp = await client.post(
        f"{ADMIN_BASE}/",
        json={
            "text": "x",
            "severity": "info",
            "enabled": True,
            "show_when": "immediately",
            "recipient_ids": [],
        },
    )
    assert resp.status_code == 422


async def test_create_rejects_unknown_recipient_id(auth_client) -> None:
    client = await auth_client(permissions=["write:settings"])
    resp = await client.post(
        f"{ADMIN_BASE}/",
        json={
            "text": "x",
            "severity": "info",
            "enabled": True,
            "show_when": "immediately",
            "recipient_ids": [999999],
        },
    )
    assert resp.status_code == 422


async def test_list_is_newest_first_and_reports_counts(auth_client, create_user) -> None:
    admin = await auth_client(permissions=["write:settings", "read:settings"])
    u1 = await create_user(username="bob", email="bob@example.com")
    u2 = await create_user(username="carol", email="carol@example.com")

    first = await _create(admin, text="first", recipient_ids=[u1.id])
    second = await _create(admin, text="second", recipient_ids=[u1.id, u2.id])

    resp = await admin.get(f"{ADMIN_BASE}/")
    assert resp.status_code == 200
    items = resp.json()
    ids_in_order = [i["public_id"] for i in items]
    assert ids_in_order.index(second["public_id"]) < ids_in_order.index(first["public_id"])

    second_item = next(i for i in items if i["public_id"] == second["public_id"])
    assert second_item["recipients_total"] == 2
    assert second_item["recipients_acknowledged"] == 0


async def test_recipients_endpoint_sorted_pending_first_then_full_name(
    auth_client, create_user, db
) -> None:
    admin = await auth_client(permissions=["write:settings", "read:settings"])
    zed = await _rename(
        db, await create_user(username="zed", email="zed@example.com"), "Zed Zephyr"
    )
    amy = await _rename(db, await create_user(username="amy", email="amy@example.com"), "Amy Adams")
    ben = await _rename(db, await create_user(username="ben", email="ben@example.com"), "Ben Baker")

    created = await _create(admin, recipient_ids=[zed.id, amy.id, ben.id])

    ben_client = await auth_client_as(ben)
    # ben acknowledges, so he must sort after the still-pending amy/zed.
    resp = await ben_client.post(
        f"{ANNOUNCEMENTS_BASE}/acknowledgements/{created['public_id']}/acknowledge"
    )
    assert resp.status_code == 204

    recipients = (await admin.get(f"{ADMIN_BASE}/{created['public_id']}/recipients")).json()
    assert [r["username"] for r in recipients] == ["amy", "zed", "ben"]
    assert recipients[-1]["acknowledged_at"] is not None
    assert recipients[0]["acknowledged_at"] is None


async def test_patch_enabled(auth_client) -> None:
    client = await auth_client(permissions=["write:settings", "read:settings"])
    created = await _create(client, recipient_ids=[1])
    resp = await client.patch(f"{ADMIN_BASE}/{created['public_id']}", json={"enabled": False})
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False

    listed = (await client.get(f"{ADMIN_BASE}/")).json()
    assert next(i for i in listed if i["public_id"] == created["public_id"])["enabled"] is False


async def test_patch_missing_404(auth_client) -> None:
    client = await auth_client(permissions=["write:settings"])
    resp = await client.patch(
        f"{ADMIN_BASE}/00000000-0000-0000-0000-000000000000", json={"enabled": False}
    )
    assert resp.status_code == 404


async def test_delete_returns_204_and_cascades_to_recipients(auth_client, create_user, db) -> None:
    client = await auth_client(permissions=["write:settings", "read:settings"])
    recipient = await create_user(username="dana", email="dana@example.com")
    created = await _create(client, recipient_ids=[recipient.id])

    ack_orm = await db.scalar(
        select(AcknowledgementOrmModel).filter_by(public_id=UUID(created["public_id"])).limit(1)
    )
    assert ack_orm is not None
    ack_id = ack_orm.id
    assert (
        await count_rows(
            db, select(AcknowledgementRecipientOrmModel).filter_by(acknowledgement_id=ack_id)
        )
        == 1
    )

    resp = await client.delete(f"{ADMIN_BASE}/{created['public_id']}")
    assert resp.status_code == 204

    db.expire_all()
    assert await db.scalar(select(AcknowledgementOrmModel).filter_by(id=ack_id).limit(1)) is None
    assert (
        await count_rows(
            db, select(AcknowledgementRecipientOrmModel).filter_by(acknowledgement_id=ack_id)
        )
        == 0
    )

    listed = (await client.get(f"{ADMIN_BASE}/")).json()
    assert all(i["public_id"] != created["public_id"] for i in listed)


async def test_delete_missing_404(auth_client) -> None:
    client = await auth_client(permissions=["write:settings"])
    resp = await client.delete(f"{ADMIN_BASE}/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


# ── User-facing /announcements ───────────────────────────────────────


async def test_me_includes_banner_with_dismissable(auth_client) -> None:
    """/announcements/me's banner carries `dismissable` straight through
    from admin_banner_settings (MyAnnouncementsBannerResult), see
    test_api_banner_settings.py for the admin-side PUT/GET round trip."""
    admin = await auth_client(permissions=["write:settings", "read:settings"])
    await admin.put(
        "/api/v1/web/admin/settings/banner",
        json={
            "enabled": True,
            "text": "We upgrade at 18:00",
            "severity": "warning",
            "dismissable": False,
        },
    )

    me = (await admin.get(f"{ANNOUNCEMENTS_BASE}/me")).json()
    assert me["banner"]["text"] == "We upgrade at 18:00"
    assert me["banner"]["dismissable"] is False


async def test_me_shows_pending_for_a_recipient_but_not_a_non_recipient(
    auth_client, create_user
) -> None:
    admin = await auth_client(permissions=["write:settings", "read:settings"])
    recipient = await create_user(username="erin", email="erin@example.com")
    outsider = await create_user(username="frank", email="frank@example.com")
    created = await _create(admin, recipient_ids=[recipient.id])

    recipient_client = await auth_client_as(recipient)
    outsider_client = await auth_client_as(outsider)

    recipient_pending = (await recipient_client.get(f"{ANNOUNCEMENTS_BASE}/me")).json()
    assert [p["public_id"] for p in recipient_pending["pending_acknowledgements"]] == [
        created["public_id"]
    ]

    outsider_pending = (await outsider_client.get(f"{ANNOUNCEMENTS_BASE}/me")).json()
    assert outsider_pending["pending_acknowledgements"] == []


async def test_disabled_acknowledgement_is_not_pending(auth_client, create_user) -> None:
    admin = await auth_client(permissions=["write:settings", "read:settings"])
    recipient = await create_user(username="gail", email="gail@example.com")
    await _create(admin, recipient_ids=[recipient.id], enabled=False)

    client = await auth_client_as(recipient)
    pending = (await client.get(f"{ANNOUNCEMENTS_BASE}/me")).json()["pending_acknowledgements"]
    assert pending == []


async def test_acknowledge_is_204_idempotent_and_then_no_longer_pending(
    auth_client, create_user
) -> None:
    admin = await auth_client(permissions=["write:settings", "read:settings"])
    recipient = await create_user(username="hank", email="hank@example.com")
    created = await _create(admin, recipient_ids=[recipient.id])

    client = await auth_client_as(recipient)
    url = f"{ANNOUNCEMENTS_BASE}/acknowledgements/{created['public_id']}/acknowledge"

    assert (await client.post(url)).status_code == 204
    assert (await client.post(url)).status_code == 204  # idempotent, still 204

    pending = (await client.get(f"{ANNOUNCEMENTS_BASE}/me")).json()["pending_acknowledgements"]
    assert pending == []

    listed = (await admin.get(f"{ADMIN_BASE}/")).json()
    assert (
        next(i for i in listed if i["public_id"] == created["public_id"])["recipients_acknowledged"]
        == 1
    )


async def test_acknowledge_non_recipient_404(auth_client, create_user) -> None:
    admin = await auth_client(permissions=["write:settings"])
    outsider = await create_user(username="ivan", email="ivan@example.com")
    other_recipient = await create_user(username="jack", email="jack@example.com")
    created = await _create(
        admin, recipient_ids=[other_recipient.id]
    )  # outsider is not a recipient

    client = await auth_client_as(outsider)
    resp = await client.post(
        f"{ANNOUNCEMENTS_BASE}/acknowledgements/{created['public_id']}/acknowledge"
    )
    assert resp.status_code == 404


async def test_next_login_ack_gated_by_session_created_at(auth_client, create_user, db) -> None:
    admin = await auth_client(permissions=["write:settings", "read:settings"])
    user = await create_user(username="june", email="june@example.com")

    before = datetime.now(UTC) - timedelta(hours=1)
    early_client = await _client_at(db, user, before)

    created = await _create(admin, recipient_ids=[user.id], show_when="next_login")

    # The session existed *before* the acknowledgement was created: not
    # delivered to it.
    pending = (await early_client.get(f"{ANNOUNCEMENTS_BASE}/me")).json()[
        "pending_acknowledgements"
    ]
    assert pending == []

    after = datetime.now(UTC) + timedelta(hours=1)
    late_client = await _client_at(db, user, after)

    # A session created after the acknowledgement (i.e. a fresh login):
    # delivered.
    pending = (await late_client.get(f"{ANNOUNCEMENTS_BASE}/me")).json()["pending_acknowledgements"]
    assert [p["public_id"] for p in pending] == [created["public_id"]]
