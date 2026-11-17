"""
Meetings over HTTP: create, read, list and edit them with their attendees,
cards with revisions, mentions, decisions and todos, validity, follow-ups
with their open points, history, files, scopes, tags, presence, the bundled
notifications, the background jobs, contact anonymisation, search and
resolving, and the permissions.
"""

import dataclasses
import io
from collections.abc import AsyncIterator
from datetime import UTC
from datetime import datetime
from datetime import timedelta

import httpx
import pytest
from PIL import Image
from sqlalchemy import select
from sqlalchemy import update

from src.bootstrap.main import app
from src.bootstrap.workers.meeting_schedule import build_meeting_ports
from src.modules.platform.adapters.inbound.api.deps.services import get_optional_storage_adapter
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.retention import (
    AdminRetentionSettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.email_notification_model import (
    EmailNotificationOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.notification_model import (
    NotificationOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.ports.outbound.storage_port import StoredObjectInfo
from src.modules.workspace.adapters.inbound.api.deps.meetings import get_meeting_presence
from src.modules.workspace.adapters.outbound.locale.meeting_activity_phrases import (
    meeting_activity_phrases,
)
from src.modules.workspace.adapters.outbound.persistence.models.meeting_model import (
    MeetingNotificationOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.meeting_model import MeetingOrmModel
from src.modules.workspace.adapters.outbound.persistence.models.meeting_model import (
    MeetingTagOrmModel,
)
from src.modules.workspace.application.use_cases.meeting.maintenance import (
    FlushMeetingNotifications,
)
from src.modules.workspace.application.use_cases.meeting.maintenance import PurgeExpiredMeetings
from src.modules.workspace.application.use_cases.meeting.maintenance import SweepOrphanMeetingFiles
from src.modules.workspace.domain.events.meeting_events import MeetingActivityDue

WRITE = [Permission.WRITE_MEETINGS, Permission.WRITE_PROJECTS, Permission.WRITE_CONTACTS]
MANAGE = [*WRITE, Permission.MANAGE_MEETINGS, Permission.READ_CONTACTS]
BASE = "/api/v1/web/meetings/"


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), "white").save(buffer, format="PNG")
    return buffer.getvalue()


class _MemoryStorage:
    """Stores blobs in a dict, with an age per key the test can set."""

    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}
        self.written: dict[str, datetime] = {}

    async def upload(self, key: str, data: bytes, content_type: str) -> None:
        self.blobs[key] = data
        self.written[key] = datetime.now(UTC)

    async def download(self, key: str) -> tuple[bytes, str]:
        return self.blobs[key], "application/octet-stream"

    async def delete(self, key: str) -> None:
        self.blobs.pop(key, None)
        self.written.pop(key, None)

    async def list_keys(self, prefix: str = "") -> list[str]:
        return [k for k in self.blobs if k.startswith(prefix)]

    async def list_objects(self, prefix: str) -> list[StoredObjectInfo]:
        return [StoredObjectInfo(k, self.written[k]) for k in self.blobs if k.startswith(prefix)]

    def get_url(self, key: str, file_name: str | None = None) -> str:
        return f"memory://{key}"


class _Presence:
    def __init__(self) -> None:
        self.calls: list[tuple[int, int, bool]] = []

    async def announce(self, card_id: int, user_id: int, *, editing: bool) -> None:
        self.calls.append((card_id, user_id, editing))


class _Bus:
    def __init__(self) -> None:
        self.events: list[object] = []

    async def publish(self, event: object) -> None:
        self.events.append(event)


@pytest.fixture
def storage() -> AsyncIterator[_MemoryStorage]:
    memory = _MemoryStorage()
    app.dependency_overrides[get_optional_storage_adapter] = lambda: memory
    yield memory
    app.dependency_overrides.pop(get_optional_storage_adapter, None)


@pytest.fixture
def presence() -> AsyncIterator[_Presence]:
    fake = _Presence()
    app.dependency_overrides[get_meeting_presence] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_meeting_presence, None)


@pytest.fixture
async def manager(auth_client):
    return await auth_client(permissions=MANAGE)


@pytest.fixture
async def writer(auth_client):
    return await auth_client(permissions=WRITE, username="writer", email="writer@example.com")


@pytest.fixture
async def reader(auth_client):
    return await auth_client(permissions=[], username="reader", email="reader@example.com")


async def _me(client: httpx.AsyncClient) -> dict:
    return (await client.get("/api/v1/web/users/me")).json()


async def _project(client, number="26-0142", **payload):
    response = await client.post(
        "/api/v1/web/projects/", json={"project_number": number, **payload}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _product(client, number="PR-0031"):
    response = await client.post("/api/v1/web/products/", json={"product_number": number})
    assert response.status_code == 201, response.text
    return response.json()


async def _contact(client, name="Thomas Muster", email="t.b@example.com"):
    response = await client.post("/api/v1/web/contacts/", json={"name": name, "email": email})
    assert response.status_code == 201, response.text
    return response.json()


def _times(day: int = 6, hour: int = 9) -> dict:
    start = datetime(2026, 11, day, hour, 0, tzinfo=UTC)
    return {"starts_at": start.isoformat(), "ends_at": (start + timedelta(hours=1)).isoformat()}


async def _meeting(client, *, project_id=None, product_id=None, **payload):
    body = {"name": "Design Review Gripper", **_times(), **payload}
    if project_id is not None:
        body["project_id"] = project_id
    if product_id is not None:
        body["product_id"] = product_id
    response = await client.post(BASE, json=body)
    assert response.status_code == 201, response.text
    return response.json()


async def _card(client, meeting_id, **payload):
    response = await client.post(f"{BASE}{meeting_id}/cards", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


# ── Meetings ──────────────────────────────────────────────────────────


class TestMeetings:
    async def test_create_read_and_list_a_project_meeting(self, manager, writer, reader):
        project = await _project(manager)
        contact = await _contact(manager)
        writer_id = (await _me(writer))["id"]

        created = await _meeting(
            manager,
            project_id=project["id"],
            location="Room Danube",
            attendees=[
                {"kind": "user", "user_id": writer_id},
                {"kind": "contact", "contact_id": contact["id"], "status": "distribution_only"},
                {"kind": "guest", "name": "Paul Lorem", "email": "p.lorem@example.com"},
            ],
        )

        assert created["meeting_number"].startswith(f"MTG-{datetime.now(UTC):%y}-")
        assert created["meeting_number"].endswith("0001")
        assert created["owner"] == {
            "kind": "project",
            "id": project["id"],
            "number": "26-0142",
            "product_id": None,
        }
        assert [(a["kind"], a["name"], a["status"]) for a in created["attendees"]] == [
            ("user", (await _me(writer))["full_name"], "present"),
            ("contact", "Thomas Muster", "distribution_only"),
            ("guest", "Paul Lorem", "present"),
        ]
        assert [a["email"] for a in created["attendees"]] == [
            (await _me(writer))["email"],
            "t.b@example.com",
            "p.lorem@example.com",
        ]
        assert created["valid"] is True and created["issue_number"] == 0

        read = await reader.get(f"{BASE}{created['id']}")
        assert read.status_code == 200
        rows = (await reader.get(BASE, params={"project_id": project["id"]})).json()
        assert [r["meeting_number"] for r in rows] == [created["meeting_number"]]
        assert rows[0]["sent"] is False and rows[0]["printed"] is False
        history = (await reader.get(f"{BASE}{created['id']}/history")).json()
        assert [e["kind"] for e in history] == ["created"]

    async def test_a_meeting_takes_the_number_format_of_the_settings(self, manager, auth_client):
        admin = await auth_client(
            permissions=[Permission.WRITE_SETTINGS], username="admin", email="admin@example.com"
        )
        saved = await admin.put(
            "/api/v1/web/admin/settings/made-items",
            json={"meeting_number_format": "BSP-{seq:03d}"},
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["meeting_example"] == "BSP-001"
        project = await _project(manager)

        created = await _meeting(manager, project_id=project["id"])

        assert created["meeting_number"] == "BSP-001"

    async def test_a_meeting_needs_exactly_one_owner_and_write_meetings(self, manager, reader):
        project = await _project(manager)
        product = await _product(manager)
        both = {"name": "X", **_times(), "project_id": project["id"], "product_id": product["id"]}

        assert (await manager.post(BASE, json=both)).status_code == 422
        assert (await manager.post(BASE, json={"name": "X", **_times()})).status_code == 422
        body = {"name": "X", **_times(), "project_id": project["id"]}
        assert (await reader.post(BASE, json=body)).status_code == 403

    async def test_an_end_before_the_start_answers_422(self, manager):
        project = await _project(manager)
        body = {
            "name": "X",
            "project_id": project["id"],
            "starts_at": "2026-11-06T10:00:00Z",
            "ends_at": "2026-11-06T09:00:00Z",
        }

        response = await manager.post(BASE, json=body)

        assert response.status_code == 422
        assert response.json()["code"] == "MeetingInvalidInputError"

    async def test_a_product_lists_its_projects_meetings_unless_asked_not_to(self, manager):
        product = await _product(manager)
        project = await _project(manager, product_id=product["id"])
        own = await _meeting(manager, product_id=product["id"], **_times(day=3))
        of_project = await _meeting(manager, project_id=project["id"], **_times(day=5))

        with_projects = (await manager.get(BASE, params={"product_id": product["id"]})).json()
        alone = (
            await manager.get(
                BASE, params={"product_id": product["id"], "include_projects": "false"}
            )
        ).json()

        assert [r["id"] for r in with_projects] == [of_project["id"], own["id"]]
        assert with_projects[0]["owner"]["product_id"] == product["id"]
        assert [r["id"] for r in alone] == [own["id"]]

    async def test_edit_checks_the_version_and_replaces_the_attendees(self, manager, writer):
        project = await _project(manager)
        writer_id = (await _me(writer))["id"]
        created = await _meeting(
            manager,
            project_id=project["id"],
            attendees=[{"kind": "guest", "name": "Paul"}],
        )
        guest_id = created["attendees"][0]["id"]
        body = {
            "name": "Renamed",
            **_times(),
            "next_meeting_date": "2026-11-20",
            "next_meeting_time": "10:30:00",
            "attendees": [
                {
                    "kind": "guest",
                    "attendee_id": guest_id,
                    "name": "Paul Lorem",
                    "status": "excused",
                },
                {"kind": "user", "user_id": writer_id},
            ],
            "expected_edit_version": created["edit_version"],
        }

        saved = await manager.put(f"{BASE}{created['id']}", json=body)
        stale = await manager.put(f"{BASE}{created['id']}", json=body)

        assert saved.status_code == 200, saved.text
        assert saved.json()["name"] == "Renamed"
        guest = saved.json()["attendees"][0]
        assert (guest["id"], guest["name"], guest["status"]) == (guest_id, "Paul Lorem", "excused")
        assert len(saved.json()["attendees"]) == 2
        assert stale.status_code == 409

    async def test_delete_needs_manage_and_hides_the_meeting(self, manager, writer):
        project = await _project(manager)
        created = await _meeting(manager, project_id=project["id"])
        url = f"{BASE}{created['id']}"
        version = {"expected_edit_version": created["edit_version"]}

        assert (await writer.delete(url, params=version)).status_code == 403
        assert (await manager.delete(url, params=version)).status_code == 204
        assert (await manager.get(url)).status_code == 404
        assert (await manager.get(BASE, params={"project_id": project["id"]})).json() == []


# ── Validity ──────────────────────────────────────────────────────────


class TestValidity:
    async def test_mark_invalid_turns_the_notes_read_only_until_restored(self, manager, writer):
        project = await _project(manager)
        created = await _meeting(manager, project_id=project["id"])
        url = f"{BASE}{created['id']}"

        assert (await writer.post(f"{url}/invalidate", json={"reason": "x"})).status_code == 403
        assert (await manager.post(f"{url}/invalidate", json={"reason": ""})).status_code == 422
        invalid = await manager.post(f"{url}/invalidate", json={"reason": "Wrong project"})
        blocked = await manager.post(f"{url}/cards", json={"body": "x"})
        restored = await manager.post(f"{url}/restore", json={"note": "Was right after all"})
        again = await manager.post(f"{url}/restore", json={})

        assert invalid.json()["valid"] is False
        assert invalid.json()["invalid_reason"] == "Wrong project"
        assert blocked.status_code == 409
        assert blocked.json()["code"] == "MeetingReadOnlyError"
        assert restored.json()["valid"] is True
        assert again.status_code == 409
        history = (await manager.get(f"{url}/history")).json()
        assert [e["kind"] for e in history][:2] == ["restored", "marked_invalid"]
        assert history[0]["summary"] == "Was right after all"
        included = (await manager.get(BASE, params={"project_id": project["id"]})).json()
        assert len(included) == 1


# ── Cards ─────────────────────────────────────────────────────────────


class TestCards:
    async def test_a_card_saves_canonical_markdown_with_its_version(self, manager, writer):
        project = await _project(manager)
        meeting = await _meeting(manager, project_id=project["id"])
        writer_id = (await _me(writer))["id"]

        card = await _card(
            manager,
            meeting["id"],
            scope="Vacuum gripper",
            scope_icon="mechanics",
            body=f"* @[Anna](user:{writer_id}) asks __the supplier__\n* @[Ghost](user:99999)",
        )

        assert card["body"] == f"- @[Anna](user:{writer_id}) asks **the supplier**\n- @Ghost"
        assert card["scope_icon"] == "mechanics"
        url = f"{BASE}{meeting['id']}/cards/{card['id']}"
        saved = await manager.put(
            url, json={"body": "Changed", "expected_edit_version": card["edit_version"]}
        )
        stale = await writer.put(
            url, json={"body": "Mine", "expected_edit_version": card["edit_version"]}
        )
        assert saved.status_code == 200
        assert saved.json()["edit_version"] > card["edit_version"]
        assert stale.status_code == 409
        assert (await manager.get(url)).json()["body"] == "Changed"

    async def test_saves_by_one_author_within_ten_minutes_share_a_revision(
        self, manager, writer, db
    ):
        project = await _project(manager)
        meeting = await _meeting(manager, project_id=project["id"])
        card = await _card(manager, meeting["id"], body="One")
        url = f"{BASE}{meeting['id']}/cards/{card['id']}"

        second = (
            await manager.put(
                url, json={"body": "Two", "expected_edit_version": card["edit_version"]}
            )
        ).json()
        third = (
            await writer.put(
                url, json={"body": "Three", "expected_edit_version": second["edit_version"]}
            )
        ).json()
        revisions = (await manager.get(f"{url}/revisions")).json()

        assert [r["body"] for r in revisions] == ["Three", "Two"]
        restored = await manager.post(
            f"{url}/revisions/{revisions[1]['id']}/restore",
            json={"expected_edit_version": third["edit_version"]},
        )
        assert restored.json()["body"] == "Two"
        assert [r["body"] for r in (await manager.get(f"{url}/revisions")).json()] == [
            "Two",
            "Three",
            "Two",
        ]
        kinds = [e["kind"] for e in (await manager.get(f"{BASE}{meeting['id']}/history")).json()]
        assert kinds.count("card_changed") == 2
        assert kinds.count("card_added") == 1

    async def test_reorder_and_delete_cards(self, manager):
        project = await _project(manager)
        meeting = await _meeting(manager, project_id=project["id"])
        first = await _card(manager, meeting["id"], scope="A")
        second = await _card(manager, meeting["id"], scope="B")

        bad = await manager.put(
            f"{BASE}{meeting['id']}/cards/order", json={"card_ids": [first["id"]]}
        )
        ordered = await manager.put(
            f"{BASE}{meeting['id']}/cards/order", json={"card_ids": [second["id"], first["id"]]}
        )
        deleted = await manager.delete(
            f"{BASE}{meeting['id']}/cards/{first['id']}",
            params={"expected_edit_version": first["edit_version"]},
        )

        assert bad.status_code == 422
        assert [c["scope"] for c in ordered.json()] == ["B", "A"]
        assert ordered.json()[1]["edit_version"] == first["edit_version"]
        assert deleted.status_code == 204
        detail = (await manager.get(f"{BASE}{meeting['id']}")).json()
        assert [c["scope"] for c in detail["cards"]] == ["B"]

    async def test_presence_is_announced_for_an_existing_card(self, manager, presence):
        project = await _project(manager)
        meeting = await _meeting(manager, project_id=project["id"])
        card = await _card(manager, meeting["id"])
        url = f"{BASE}{meeting['id']}/cards/{card['id']}/presence"

        assert (await manager.post(url, json={"editing": True})).status_code == 204
        assert (await manager.post(url, json={"editing": False})).status_code == 204
        missing = await manager.post(f"{BASE}{meeting['id']}/cards/999/presence", json={})

        manager_id = (await _me(manager))["id"]
        assert presence.calls == [(card["id"], manager_id, True), (card["id"], manager_id, False)]
        assert missing.status_code == 404


# ── Decisions and todos ───────────────────────────────────────────────


class TestTodos:
    async def test_decisions_are_added_edited_and_removed(self, manager):
        project = await _project(manager)
        meeting = await _meeting(manager, project_id=project["id"])
        card = await _card(manager, meeting["id"])

        created = await manager.post(
            f"{BASE}{meeting['id']}/cards/{card['id']}/decisions", json={"text": "FKM cups"}
        )
        url = f"{BASE}{meeting['id']}/decisions/{created.json()['id']}"
        edited = await manager.put(url, json={"text": "FKM cups from week 47"})
        detail = (await manager.get(f"{BASE}{meeting['id']}")).json()
        removed = await manager.delete(url)

        assert created.status_code == 201
        assert edited.json()["text"] == "FKM cups from week 47"
        assert [d["text"] for d in detail["cards"][0]["decisions"]] == ["FKM cups from week 47"]
        assert removed.status_code == 204

    async def test_todo_owners_counts_and_ticking_off(self, manager, auth_client):
        project = await _project(manager)
        contact = await _contact(manager)
        owner = await auth_client(permissions=[], username="owner", email="owner@example.com")
        other = await auth_client(permissions=[], username="other", email="other@example.com")
        owner_id = (await _me(owner))["id"]
        meeting = await _meeting(manager, project_id=project["id"])
        card = await _card(manager, meeting["id"])
        todos_url = f"{BASE}{meeting['id']}/cards/{card['id']}/todos"

        late = await manager.post(
            todos_url,
            json={
                "title": "Order samples",
                "due_date": "2020-01-01",
                "owners": [{"user_id": owner_id}, {"contact_id": contact["id"]}],
            },
        )
        await manager.post(todos_url, json={"title": "Undated"})
        todo = late.json()

        assert late.status_code == 201, late.text
        assert sorted(o["name"] for o in todo["owners"]) == sorted(
            [(await _me(owner))["full_name"], "Thomas Muster"]
        )
        row = (await manager.get(BASE, params={"project_id": project["id"]})).json()[0]
        assert (row["open_todo_count"], row["overdue_todo_count"]) == (2, 1)

        todo_url = f"{BASE}{meeting['id']}/todos/{todo['id']}"
        assert (await other.post(f"{todo_url}/done")).status_code == 403
        done = await owner.post(f"{todo_url}/done")
        assert done.status_code == 200
        assert done.json()["done"] is True
        assert done.json()["done_by"]["id"] == owner_id
        reopened = await manager.post(f"{todo_url}/reopen")
        assert reopened.json()["done"] is False
        kinds = [e["kind"] for e in (await manager.get(f"{BASE}{meeting['id']}/history")).json()]
        assert kinds[:3] == ["todo_reopened", "todo_done", "todo_added"]


# ── Notifications ─────────────────────────────────────────────────────


class TestNotifications:
    async def test_mentions_and_assignments_are_bundled_and_sent_once_due(
        self, manager, writer, db
    ):
        project = await _project(manager)
        writer_me = await _me(writer)
        manager_me = await _me(manager)
        meeting = await _meeting(manager, project_id=project["id"])
        mention = f"@[Writer](user:{writer_me['id']}) and @[Me](user:{manager_me['id']})"
        card = await _card(manager, meeting["id"], body=mention)
        await _card(manager, meeting["id"], body=f"@[Writer](user:{writer_me['id']})")
        await manager.post(
            f"{BASE}{meeting['id']}/cards/{card['id']}/todos",
            json={"title": "A", "owners": [{"user_id": writer_me["id"]}]},
        )
        # Saving the card again mentions nobody new.
        await manager.put(
            f"{BASE}{meeting['id']}/cards/{card['id']}",
            json={"body": mention + " again", "expected_edit_version": card["edit_version"]},
        )

        rows = (await db.scalars(select(MeetingNotificationOrmModel))).all()
        assert [(r.recipient_id, r.mention_count, r.todo_count) for r in rows] == [
            (writer_me["id"], 2, 1)
        ]

        bus = _Bus()
        ports = await build_meeting_ports(db)
        assert (
            await FlushMeetingNotifications(ports, bus, meeting_activity_phrases()).execute() == 0
        )
        await db.execute(
            update(MeetingNotificationOrmModel).values(
                first_at=datetime.now(UTC) - timedelta(minutes=6)
            )
        )
        await db.commit()
        assert (
            await FlushMeetingNotifications(ports, bus, meeting_activity_phrases()).execute() == 1
        )

        (event,) = bus.events
        assert isinstance(event, MeetingActivityDue)
        first_name = manager_me["full_name"].split()[0]
        assert event.message == (
            f"{first_name} mentioned you twice and assigned you 1 todo in "
            f"{meeting['meeting_number']}"
        )
        assert (await db.scalars(select(MeetingNotificationOrmModel))).all() == []

    async def test_a_german_recipient_reads_the_bundled_notification_in_german(
        self, manager, writer, db
    ):
        project = await _project(manager)
        writer_me = await _me(writer)
        manager_me = await _me(manager)
        await db.execute(
            update(UserOrmModel).where(UserOrmModel.id == writer_me["id"]).values(language="deAT")
        )
        await db.commit()
        meeting = await _meeting(manager, project_id=project["id"])
        card = await _card(manager, meeting["id"], body=f"@[Writer](user:{writer_me['id']})")
        await manager.post(
            f"{BASE}{meeting['id']}/cards/{card['id']}/todos",
            json={"title": "A", "owners": [{"user_id": writer_me["id"]}]},
        )
        await db.execute(
            update(MeetingNotificationOrmModel).values(
                first_at=datetime.now(UTC) - timedelta(minutes=6)
            )
        )
        await db.commit()

        bus = _Bus()
        flush = FlushMeetingNotifications(
            await build_meeting_ports(db), bus, meeting_activity_phrases()
        )
        assert await flush.execute() == 1

        (event,) = bus.events
        first_name = manager_me["full_name"].split()[0]
        number = meeting["meeting_number"]
        german = meeting_activity_phrases()[Language.deAT]
        assert event.message == german.one_actor.mentions_and_todos.format(
            names=first_name, times=german.once, todos=german.one_todo, meeting=number
        )
        assert event.title == german.title.format(meeting=number)


# ── Follow-ups ────────────────────────────────────────────────────────


class TestFollowUp:
    async def test_follow_up_takes_the_next_meeting_and_shows_open_points(self, manager):
        project = await _project(manager)
        first = await _meeting(
            manager,
            project_id=project["id"],
            location="Room Danube",
            next_meeting_date="2026-11-20",
            next_meeting_time="10:00:00",
            next_meeting_location="Teams",
            attendees=[{"kind": "guest", "name": "Paul", "status": "excused"}],
        )
        card = await _card(manager, first["id"], scope="Gripper")
        await manager.post(
            f"{BASE}{first['id']}/cards/{card['id']}/todos", json={"title": "Open one"}
        )

        follow = await manager.post(f"{BASE}{first['id']}/follow-up")
        body = follow.json()
        second = await manager.post(f"{BASE}{body['id']}/follow-up")
        points = (await manager.get(f"{BASE}{second.json()['id']}/open-points")).json()

        assert follow.status_code == 201, follow.text
        assert body["name"] == first["name"]
        assert body["location"] == "Teams"
        assert body["follow_up_of"]["id"] == first["id"]
        # 10:00 in Vienna on 20 November is 09:00 UTC.
        assert body["starts_at"].startswith("2026-11-20T09:00")
        assert [(a["name"], a["status"]) for a in body["attendees"]] == [("Paul", "excused")]
        assert [(p["todo"]["title"], p["meeting"]["id"], p["card_scope"]) for p in points] == [
            ("Open one", first["id"], "Gripper")
        ]


# ── Scopes ────────────────────────────────────────────────────────────


class TestScopes:
    async def test_suggestions_rank_by_use_and_name_a_near_duplicate(self, manager):
        product = await _product(manager)
        project = await _project(manager, product_id=product["id"])
        on_product = await _meeting(manager, product_id=product["id"])
        on_project = await _meeting(manager, project_id=project["id"])
        await _card(manager, on_product["id"], scope="Vacuum gripper", scope_icon="mechanics")
        await _card(manager, on_project["id"], scope="Vacuum gripper")
        await _card(manager, on_project["id"], scope="Schedule")

        body = (
            await manager.get(
                "/api/v1/web/meeting-scopes/",
                params={"project_id": project["id"], "q": "vacum  Gripper"},
            )
        ).json()
        everything = (
            await manager.get("/api/v1/web/meeting-scopes/", params={"product_id": product["id"]})
        ).json()

        assert body["near_duplicate"] == "Vacuum gripper"
        assert [(s["scope"], s["count"]) for s in everything["suggestions"]] == [
            ("Vacuum gripper", 2),
            ("Schedule", 1),
        ]
        assert everything["suggestions"][0]["icon"] == "mechanics"

    async def test_rename_reaches_the_product_and_its_projects(self, manager):
        product = await _product(manager)
        project = await _project(manager, product_id=product["id"])
        on_project = await _meeting(manager, project_id=project["id"])
        card = await _card(manager, on_project["id"], scope="Gripper")

        renamed = await manager.post(
            "/api/v1/web/meeting-scopes/rename",
            json={"product_id": product["id"], "from_scope": "Gripper", "to_scope": "Gripper V2"},
        )

        assert renamed.json() == {"renamed": 1}
        fetched = await manager.get(f"{BASE}{on_project['id']}/cards/{card['id']}")
        assert fetched.json()["scope"] == "Gripper V2"


# ── Tags ──────────────────────────────────────────────────────────────

TAGS = "/api/v1/web/meeting-tags/"


class TestTags:
    async def test_create_normalises_the_tags_and_drops_repeats(self, manager):
        project = await _project(manager)

        created = await _meeting(
            manager,
            project_id=project["id"],
            tags=["  Milestone ", "", "Factory   acceptance", "milestone", "   ", "Risk"],
        )
        without = await _meeting(manager, project_id=project["id"])

        assert created["tags"] == ["Milestone", "Factory acceptance", "Risk"]
        assert without["tags"] == []
        rows = (await manager.get(BASE, params={"project_id": project["id"]})).json()
        assert {r["id"]: r["tags"] for r in rows} == {
            created["id"]: ["Milestone", "Factory acceptance", "Risk"],
            without["id"]: [],
        }

    async def test_a_long_tag_or_too_many_tags_answer_422(self, manager):
        project = await _project(manager)
        base = {"name": "X", **_times(), "project_id": project["id"]}

        too_long = await manager.post(BASE, json={**base, "tags": ["x" * 41]})
        longest = await manager.post(BASE, json={**base, "tags": ["x" * 40]})
        too_many = await manager.post(BASE, json={**base, "tags": [f"T{i}" for i in range(11)]})
        ten_after_repeats = await manager.post(
            BASE, json={**base, "tags": [f"T{i}" for i in range(10)] + ["t0", "T9"]}
        )

        assert too_long.status_code == 422
        assert too_long.json()["code"] == "MeetingInvalidInputError"
        assert longest.status_code == 201, longest.text
        assert too_many.status_code == 422
        assert too_many.json()["code"] == "MeetingInvalidInputError"
        assert ten_after_repeats.status_code == 201, ten_after_repeats.text
        assert len(ten_after_repeats.json()["tags"]) == 10

    async def test_edit_replaces_the_tags_in_their_new_order(self, manager):
        project = await _project(manager)
        created = await _meeting(manager, project_id=project["id"], tags=["Milestone", "Risk"])
        body = {
            "name": created["name"],
            **_times(),
            "tags": ["risk", "Acceptance", "Milestone"],
            "expected_edit_version": created["edit_version"],
        }

        saved = await manager.put(f"{BASE}{created['id']}", json=body)
        cleared = await manager.put(
            f"{BASE}{created['id']}",
            json={**body, "tags": [], "expected_edit_version": saved.json()["edit_version"]},
        )

        assert saved.status_code == 200, saved.text
        assert saved.json()["tags"] == ["risk", "Acceptance", "Milestone"]
        assert saved.json()["edit_version"] > created["edit_version"]
        assert cleared.status_code == 200, cleared.text
        assert cleared.json()["tags"] == []
        history = (await manager.get(f"{BASE}{created['id']}/history")).json()
        assert [e["kind"] for e in history] == ["edited", "edited", "created"]

    async def test_an_attendee_only_edit_refuses_a_stale_save(self, manager):
        project = await _project(manager)
        created = await _meeting(manager, project_id=project["id"])
        body = {
            "name": created["name"],
            "starts_at": created["starts_at"],
            "ends_at": created["ends_at"],
            "location": created["location"],
            "tags": created["tags"],
            "attendees": [{"kind": "guest", "name": "Paul Lorem"}],
            "expected_edit_version": created["edit_version"],
        }

        saved = await manager.put(f"{BASE}{created['id']}", json=body)
        stale = await manager.put(f"{BASE}{created['id']}", json=body)

        assert saved.status_code == 200, saved.text
        assert saved.json()["edit_version"] > created["edit_version"]
        assert stale.status_code == 409

    async def test_the_list_filters_by_a_tag_in_any_case(self, manager):
        product = await _product(manager)
        project = await _project(manager, product_id=product["id"])
        tagged = await _meeting(
            manager, project_id=project["id"], tags=["Factory acceptance"], **_times(day=5)
        )
        await _meeting(manager, project_id=project["id"], tags=["Milestone"])
        on_product = await _meeting(
            manager, product_id=product["id"], tags=["factory ACCEPTANCE"], **_times(day=3)
        )

        rows = (
            await manager.get(
                BASE, params={"product_id": product["id"], "tag": " FACTORY  acceptance "}
            )
        ).json()
        none = (
            await manager.get(BASE, params={"project_id": project["id"], "tag": "factory"})
        ).json()
        blank = (await manager.get(BASE, params={"project_id": project["id"], "tag": ""})).json()

        assert [r["id"] for r in rows] == [tagged["id"], on_product["id"]]
        assert none == []
        assert len(blank) == 2

    async def test_suggestions_rank_the_tags_in_use_by_meetings(self, manager, reader):
        first = await _project(manager)
        second = await _project(manager, number="26-0143")
        await _meeting(manager, project_id=first["id"], tags=["Milestone", "Risk"])
        await _meeting(manager, project_id=second["id"], tags=["milestone", "Acceptance"])
        await _meeting(manager, project_id=second["id"], tags=["Milestone"])
        deleted = await _meeting(manager, project_id=first["id"], tags=["Gone"])
        await manager.delete(
            f"{BASE}{deleted['id']}", params={"expected_edit_version": deleted["edit_version"]}
        )

        everything = await reader.get(TAGS)
        narrowed = (await reader.get(TAGS, params={"q": "S"})).json()
        capped = (await reader.get(TAGS, params={"limit": 1})).json()

        assert everything.status_code == 200, everything.text
        assert [(s["name"], s["count"]) for s in everything.json()["suggestions"]] == [
            ("Milestone", 3),
            ("Acceptance", 1),
            ("Risk", 1),
        ]
        assert [s["name"] for s in narrowed["suggestions"]] == ["Milestone", "Risk"]
        assert [s["name"] for s in capped["suggestions"]] == ["Milestone"]

    async def test_a_follow_up_copies_the_tags(self, manager):
        project = await _project(manager)
        first = await _meeting(manager, project_id=project["id"], tags=["Milestone", "Risk"])

        follow = await manager.post(f"{BASE}{first['id']}/follow-up")

        assert follow.status_code == 201, follow.text
        assert follow.json()["tags"] == ["Milestone", "Risk"]

    async def test_a_purge_removes_the_tags_with_the_meeting(self, manager, storage, db):
        project = await _project(manager)
        await _meeting(manager, project_id=project["id"], tags=["Milestone"])
        db.add(AdminRetentionSettingsOrmModel(id=1, meeting_retention_days=1))
        await db.commit()
        ports = dataclasses.replace(await build_meeting_ports(db), storage=storage)

        assert await PurgeExpiredMeetings(ports).execute() == 1
        assert (await db.scalars(select(MeetingTagOrmModel))).all() == []


# ── Files ─────────────────────────────────────────────────────────────


class TestFiles:
    async def test_upload_link_into_a_card_and_delete(self, manager, storage):
        project = await _project(manager)
        meeting = await _meeting(manager, project_id=project["id"])
        card = await _card(manager, meeting["id"])

        uploaded = await manager.post(
            f"{BASE}{meeting['id']}/files",
            data={"category": "image", "card_id": str(card["id"])},
            files={"file": ("rig.png", _png(), "image/png")},
        )
        file = uploaded.json()
        saved = await manager.put(
            f"{BASE}{meeting['id']}/cards/{card['id']}",
            json={
                "body": f"![rig](file:{file['id']}) ![x](file:999)",
                "expected_edit_version": card["edit_version"],
            },
        )
        downloaded = await manager.get(f"{BASE}{meeting['id']}/files/{file['id']}")
        deleted = await manager.delete(f"{BASE}{meeting['id']}/files/{file['id']}")

        assert uploaded.status_code == 201, uploaded.text
        assert file["card_id"] == card["id"]
        assert file["storage_path"].startswith(f"meetings/{meeting['id']}/image/")
        assert saved.json()["body"] == f"![rig](file:{file['id']}) x"
        assert downloaded.status_code == 200
        assert deleted.status_code == 204
        assert storage.blobs == {}
        kinds = [e["kind"] for e in (await manager.get(f"{BASE}{meeting['id']}/history")).json()]
        assert kinds[:2] == ["file_deleted", "file_added"]

    async def test_renaming_a_file_keeps_its_card(self, manager, storage):
        project = await _project(manager)
        meeting = await _meeting(manager, project_id=project["id"])
        card = await _card(manager, meeting["id"])
        file = (
            await manager.post(
                f"{BASE}{meeting['id']}/files",
                data={"category": "image", "card_id": str(card["id"])},
                files={"file": ("rig.png", _png(), "image/png")},
            )
        ).json()
        url = f"{BASE}{meeting['id']}/files/{file['id']}"

        renamed = await manager.patch(url, json={"file_name": "Test rig.png"})

        assert renamed.status_code == 200, renamed.text
        assert (renamed.json()["file_name"], renamed.json()["card_id"]) == (
            "Test rig.png",
            card["id"],
        )
        assert (await manager.patch(url, json={"file_name": ""})).status_code == 422
        elsewhere = await manager.patch(
            f"{BASE}{meeting['id'] + 99}/files/{file['id']}", json={"file_name": "x.png"}
        )
        assert elsewhere.status_code == 404

    async def test_the_sweep_removes_old_blobs_no_row_names(self, manager, storage, db):
        project = await _project(manager)
        meeting = await _meeting(manager, project_id=project["id"])
        kept = (
            await manager.post(
                f"{BASE}{meeting['id']}/files",
                data={"category": "pdf"},
                files={"file": ("a.pdf", b"%PDF-1.4", "application/pdf")},
            )
        ).json()
        old = datetime.now(UTC) - timedelta(days=2)
        storage.blobs["meetings/1/pdf/orphan.pdf"] = b"x"
        storage.written["meetings/1/pdf/orphan.pdf"] = old
        storage.blobs["meetings/1/pdf/fresh.pdf"] = b"x"
        storage.written["meetings/1/pdf/fresh.pdf"] = datetime.now(UTC)
        storage.written[kept["storage_path"]] = old

        ports = dataclasses.replace(await build_meeting_ports(db), storage=storage)
        removed = await SweepOrphanMeetingFiles(ports).execute()

        assert removed == 1
        assert sorted(storage.blobs) == sorted([kept["storage_path"], "meetings/1/pdf/fresh.pdf"])

    async def test_retention_purges_old_meetings_with_their_files(self, manager, storage, db):
        project = await _project(manager)
        meeting = await _meeting(manager, project_id=project["id"])
        await _card(manager, meeting["id"], body="Old notes")
        await manager.post(
            f"{BASE}{meeting['id']}/files",
            data={"category": "pdf"},
            files={"file": ("a.pdf", b"%PDF-1.4", "application/pdf")},
        )
        db.add(AdminRetentionSettingsOrmModel(id=1))
        await db.commit()
        ports = dataclasses.replace(await build_meeting_ports(db), storage=storage)

        assert (await ports.settings.get_retention()).meeting_retention_days == 0
        assert await PurgeExpiredMeetings(ports).execute() == 0
        settings = await ports.settings.get_retention()
        settings.meeting_retention_days = 1
        await ports.settings.save_retention(settings)
        await db.commit()

        assert await PurgeExpiredMeetings(ports).execute() == 1
        assert storage.blobs == {}
        assert (await db.scalars(select(MeetingOrmModel))).all() == []


# ── Contacts, anonymising ─────────────────────────────────────────────


class TestAnonymise:
    async def test_anonymising_a_contact_blanks_its_copies(self, manager, auth_client):
        project = await _project(manager)
        contact = await _contact(manager)
        meeting = await _meeting(
            manager,
            project_id=project["id"],
            attendees=[{"kind": "contact", "contact_id": contact["id"]}],
        )
        card = await _card(manager, meeting["id"])
        await manager.post(
            f"{BASE}{meeting['id']}/cards/{card['id']}/todos",
            json={"title": "Confirm", "owners": [{"contact_id": contact["id"]}]},
        )
        contacts_only = await auth_client(
            permissions=[Permission.READ_CONTACTS, Permission.WRITE_CONTACTS],
            username="contacts",
            email="contacts@example.com",
        )

        refused = await contacts_only.post(f"/api/v1/web/contacts/{contact['id']}/anonymise")
        done = await manager.post(f"/api/v1/web/contacts/{contact['id']}/anonymise")
        detail = (await manager.get(f"{BASE}{meeting['id']}")).json()

        assert refused.status_code == 403
        assert done.status_code == 200
        assert (detail["attendees"][0]["name"], detail["attendees"][0]["email"]) == ("", None)
        assert detail["attendees"][0]["anonymised"] is True
        assert detail["cards"][0]["todos"][0]["owners"][0]["name"] == ""

    async def test_a_guest_is_anonymised_on_the_meeting(self, manager, writer):
        project = await _project(manager)
        meeting = await _meeting(
            manager,
            project_id=project["id"],
            attendees=[{"kind": "guest", "name": "Paul", "email": "p@example.com"}],
        )
        url = f"{BASE}{meeting['id']}/attendees/{meeting['attendees'][0]['id']}/anonymise"

        assert (await writer.post(url)).status_code == 403
        body = (await manager.post(url)).json()

        assert (body["attendees"][0]["name"], body["attendees"][0]["email"]) == ("", None)


# ── Search, resolving, notifications ──────────────────────────────────


class TestAround:
    async def test_search_finds_a_meeting_by_number_and_name(self, manager):
        project = await _project(manager)
        meeting = await _meeting(manager, project_id=project["id"], name="Kick-off Line 2")

        by_name = (await manager.get("/api/v1/web/search/", params={"q": "kick-off"})).json()
        by_number = (
            await manager.get("/api/v1/web/search/", params={"q": meeting["meeting_number"]})
        ).json()

        for body in (by_name, by_number):
            group = next(g for g in body["groups"] if g["resource"] == "meetings")
            assert [hit["id"] for hit in group["items"]] == [meeting["id"]]
            assert group["items"][0]["label"] == meeting["meeting_number"]

    async def test_a_meeting_resolves_by_its_public_id(self, manager):
        project = await _project(manager)
        meeting = await _meeting(manager, project_id=project["id"])

        resolved = (await manager.get(f"/api/v1/web/resolve/{meeting['public_id']}")).json()

        assert resolved["resource"] == "meetings"
        assert resolved["id"] == meeting["id"]

    async def test_the_notification_rule_writes_the_deep_link_and_the_digest_entry(
        self, manager, db
    ):
        from src.modules.platform.adapters.outbound.persistence.repositories.email_notification_repository import (
            SqlAlchemyEmailNotificationRepository,
        )
        from src.modules.platform.adapters.outbound.persistence.repositories.notification_repository import (
            SqlAlchemyNotificationRepository,
        )
        from src.modules.platform.adapters.outbound.persistence.unit_of_work import (
            SqlAlchemyUnitOfWork,
        )
        from src.modules.platform.application.use_cases.notification.handle_event_notifications import (
            HandleEventNotifications,
        )

        me = await _me(manager)
        project = await _project(manager)
        meeting = await _meeting(manager, project_id=project["id"])
        event = MeetingActivityDue(
            meeting_id=meeting["id"],
            meeting_number=meeting["meeting_number"],
            recipient_id=me["id"],
            mention_count=1,
            todo_count=0,
            message="Anna mentioned you once in MTG",
        )

        await HandleEventNotifications(
            SqlAlchemyNotificationRepository(db),
            SqlAlchemyEmailNotificationRepository(db),
            uow=SqlAlchemyUnitOfWork(db),
        ).execute(event, "event-1")

        notification = (await manager.get("/api/v1/web/notifications/")).json()["items"][0]
        assert notification["meeting_id"] == meeting["id"]
        assert notification["type"] == "meeting_mentioned"
        assert notification["message"] == "Anna mentioned you once in MTG."
        entry = (await db.scalars(select(EmailNotificationOrmModel))).one()
        assert (entry.reason, entry.meeting_id) == ("meeting", meeting["id"])
        assert (await db.scalars(select(NotificationOrmModel))).one().project_id is None
