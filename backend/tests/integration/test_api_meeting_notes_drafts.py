"""
Drafts of meeting notes: an agent submits notes it read through the MCP
tool draft_meeting_notes, the token's owner alone sees the draft with the
users and contacts suggested for its names, and applying the reviewed form
creates the meeting or adds to it, appends the cards with their decisions
and todos, queues the todo notifications and deletes the draft. Nothing
changes before the apply. Also the meetings read tool, discarding, the
retention purge and who sees the tools.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.adapters.outbound.persistence.models.meeting_model import (
    MeetingNotificationOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.meeting_notes_draft_repository import (
    SqlAlchemyMeetingNotesDraftRepository,
)
from src.modules.workspace.application.use_cases.meeting.notes_drafts import (
    PurgeExpiredMeetingNotesDrafts,
)
from src.modules.workspace.domain.entities.meeting_notes_draft import DraftCard
from src.modules.workspace.domain.entities.meeting_notes_draft import MeetingNotesDraft
from tests.integration._mcp_helpers import call_tool
from tests.integration._mcp_helpers import list_tool_names
from tests.integration._mcp_helpers import logged_calls
from tests.integration._mcp_helpers import mint_agent_token
from tests.integration._mcp_helpers import save_agent_settings
from tests.integration.conftest import auth_headers

DRAFTS = "/api/v1/web/meeting-notes-drafts/"
MEETINGS = "/api/v1/web/meetings/"
AGENT = [Permission.USE_MCP, Permission.WRITE_MEETINGS]
START = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
async def agents_on(db: AsyncSession) -> None:
    await save_agent_settings(db)


async def _user(
    db: AsyncSession,
    create_user: Callable[..., Awaitable[User]],
    username: str,
    full_name: str,
    permissions: list[str],
) -> User:
    user = await create_user(
        username=username, email=f"{username}@example.com", permissions=permissions
    )
    saved = await SqlAlchemyUserRepository(db).save(replace(user, full_name=full_name))
    await db.commit()
    return saved


@pytest.fixture
async def owner(db: AsyncSession, create_user: Callable[..., Awaitable[User]]) -> User:
    return await _user(
        db,
        create_user,
        "planner",
        "Petra Planner",
        [
            Permission.WRITE_PAT,
            Permission.WRITE_PROJECTS,
            Permission.READ_CONTACTS,
            Permission.WRITE_CONTACTS,
            *AGENT,
        ],
    )


@pytest.fixture
async def colleague(db: AsyncSession, create_user: Callable[..., Awaitable[User]]) -> User:
    return await _user(db, create_user, "hmueller", "Hans Müller", [])


@pytest.fixture
async def web(client: httpx.AsyncClient, owner: User) -> httpx.AsyncClient:
    client.headers.update(await auth_headers(owner))
    return client


@pytest.fixture
async def token(db: AsyncSession, owner: User) -> str:
    return await mint_agent_token(db, owner, AGENT, name="Notebook agent")


async def _project(web: httpx.AsyncClient, number: str = "26-0142") -> dict[str, Any]:
    response = await web.post("/api/v1/web/projects/", json={"project_number": number})
    assert response.status_code == 201, response.text
    return response.json()


async def _meeting(web: httpx.AsyncClient, project_id: int, **payload: Any) -> dict[str, Any]:
    body = {
        "name": "Design review",
        "starts_at": START.isoformat(),
        "ends_at": (START + timedelta(hours=1)).isoformat(),
        "project_id": project_id,
        **payload,
    }
    response = await web.post(MEETINGS, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _data(result: dict[str, Any]) -> dict[str, Any]:
    assert result["isError"] is False, result["content"][0]["text"]
    data: dict[str, Any] = result["structuredContent"]
    return data


def _card(**values: Any) -> dict[str, Any]:
    return {
        "scope": "Electrical cabinet",
        "scope_icon": "electrical",
        "body": "Cabinet layout agreed.\n\n- Door hinge left",
        "decisions": ["Use the 800 mm cabinet"],
        "todos": [{"title": "Send the layout", "owners": ["Hans M."], "due_date": "2026-11-20"}],
        **values,
    }


async def _draft_new(client: httpx.AsyncClient, token: str, **values: Any) -> dict[str, Any]:
    arguments = {
        "project_number": "26-0142",
        "new_meeting_name": "Kick-off cabinet",
        "new_meeting_starts_at": START.isoformat(),
        "new_meeting_ends_at": (START + timedelta(hours=2)).isoformat(),
        "attendees": [
            {"name": "Hans M."},
            {"name": "Erika (Lieferant GmbH)", "status": "excused"},
        ],
        "cards": [_card(review_note="Second line unreadable")],
        "review_note": "Photo of two notebook pages",
        **values,
    }
    return _data(await call_tool(client, token, "draft_meeting_notes", arguments))


async def _queued(db: AsyncSession) -> list[MeetingNotificationOrmModel]:
    db.expire_all()
    return list((await db.execute(select(MeetingNotificationOrmModel))).scalars())


async def test_a_draft_of_a_new_meeting_changes_nothing_until_its_owner_applies_it(
    client: httpx.AsyncClient,
    db: AsyncSession,
    web: httpx.AsyncClient,
    token: str,
    owner: User,
    colleague: User,
    auth_client: Callable[..., Awaitable[httpx.AsyncClient]],
) -> None:
    project = await _project(web)
    result = await _draft_new(client, token)
    draft_id = result["draft"]["id"]
    assert result["draft"]["owner_number"] == "26-0142"
    assert result["review_path"] == f"/meeting-notes-drafts/{draft_id}"

    # Nothing exists yet but the draft, and nobody else sees it.
    meetings = await web.get(MEETINGS, params={"project_id": project["id"]})
    assert meetings.json() == []
    other = await auth_client(permissions=AGENT, username="other", email="other@example.com")
    assert (await other.get(DRAFTS)).json() == []
    assert (await other.get(f"{DRAFTS}{draft_id}")).status_code == 404
    log = await logged_calls(db)
    assert log[-1].created_refs and log[-1].created_refs[0].startswith("meeting_notes_draft:")

    listed = (await web.get(DRAFTS, params={"project_id": project["id"]})).json()
    assert [(d["id"], d["name"], d["card_count"], d["todo_count"]) for d in listed] == [
        (draft_id, "Kick-off cabinet", 1, 1)
    ]
    assert listed[0]["token_name"] == "Notebook agent"

    detail = (await web.get(f"{DRAFTS}{draft_id}")).json()
    assert detail["cards"][0]["review_note"] == "Second line unreadable"
    people = {p["written"]: p for p in detail["people"]}
    assert set(people) == {"Hans M.", "Erika (Lieferant GmbH)"}
    assert people["Hans M."]["best"] == {
        "kind": "user",
        "id": colleague.id,
        "name": "Hans Müller",
    }
    assert people["Erika (Lieferant GmbH)"]["best"] is None

    applied = await web.post(
        f"{DRAFTS}{draft_id}/apply",
        json={
            "new_meeting": {
                "name": "Kick-off cabinet",
                "starts_at": START.isoformat(),
                "ends_at": (START + timedelta(hours=2)).isoformat(),
            },
            "attendees": [
                {"kind": "user", "user_id": colleague.id},
                {"kind": "guest", "name": "Erika", "status": "excused"},
            ],
            "cards": [
                {
                    "scope": "Electrical cabinet",
                    "scope_icon": "electrical",
                    "body": detail["cards"][0]["body"],
                    "decisions": ["Use the 800 mm cabinet"],
                    "todos": [
                        {
                            "title": "Send the layout",
                            "due_date": "2026-11-20",
                            "owners": [{"user_id": colleague.id}],
                        }
                    ],
                }
            ],
        },
    )
    assert applied.status_code == 200, applied.text
    meeting = applied.json()["meeting"]
    assert meeting["name"] == "Kick-off cabinet"
    assert [(a["kind"], a["name"]) for a in meeting["attendees"]] == [
        ("user", "Hans Müller"),
        ("guest", "Erika"),
    ]
    card = meeting["cards"][0]
    assert card["scope"] == "Electrical cabinet"
    assert [d["text"] for d in card["decisions"]] == ["Use the 800 mm cabinet"]
    assert [t["title"] for t in card["todos"]] == ["Send the layout"]

    history = (await web.get(f"{MEETINGS}{meeting['id']}/history")).json()
    assert sorted(e["kind"] for e in history) == ["created", "imported"]
    assert [q.recipient_id for q in await _queued(db)] == [colleague.id]
    assert (await web.get(f"{DRAFTS}{draft_id}")).status_code == 404


async def test_a_draft_adds_to_an_existing_meeting_without_duplicating_attendees(
    client: httpx.AsyncClient, db: AsyncSession, web: httpx.AsyncClient, token: str, colleague: User
) -> None:
    project = await _project(web)
    meeting = await _meeting(
        web, project["id"], attendees=[{"kind": "user", "user_id": colleague.id}]
    )
    first = await web.post(f"{MEETINGS}{meeting['id']}/cards", json={"body": "Typed live"})
    assert first.status_code == 201, first.text

    listed = _data(await call_tool(client, token, "meetings", {"project_number": "26-0142"}))
    assert [m["meeting_number"] for m in listed["items"]] == [meeting["meeting_number"]]
    assert set(listed["items"][0]) == {
        "meeting_number",
        "name",
        "owner_number",
        "starts_at",
        "ends_at",
        "location",
        "tags",
        "card_count",
        "open_todo_count",
    }

    result = _data(
        await call_tool(
            client,
            token,
            "draft_meeting_notes",
            {
                "project_number": "26-0142",
                "meeting_number": meeting["meeting_number"],
                "attendees": [{"name": "Hans Müller"}, {"name": "Paul Lorem"}],
                "cards": [_card(todos=[])],
                "next_meeting_date": "2026-11-24",
            },
        )
    )
    draft_id = result["draft"]["id"]
    assert result["draft"]["meeting_number"] == meeting["meeting_number"]
    unchanged = (await web.get(f"{MEETINGS}{meeting['id']}")).json()
    assert len(unchanged["cards"]) == 1 and unchanged["next_meeting_date"] is None

    applied = await web.post(
        f"{DRAFTS}{draft_id}/apply",
        json={
            "attendees": [
                {"kind": "user", "user_id": colleague.id},
                {"kind": "guest", "name": "Paul Lorem"},
            ],
            "cards": [{"body": "From the notebook", "decisions": ["Go"]}],
            "next_meeting_date": "2026-11-24",
        },
    )
    assert applied.status_code == 200, applied.text
    after = applied.json()["meeting"]
    assert [(a["kind"], a["name"]) for a in after["attendees"]] == [
        ("user", "Hans Müller"),
        ("guest", "Paul Lorem"),
    ]
    assert [c["body"] for c in after["cards"]] == ["Typed live", "From the notebook"]
    assert after["next_meeting_date"] == "2026-11-24"


async def test_a_draft_never_mentions_anybody(
    client: httpx.AsyncClient, db: AsyncSession, web: httpx.AsyncClient, token: str, colleague: User
) -> None:
    await _project(web)
    body = f"Ask @[Hans Müller](user:{colleague.id}) about it ![x](file:1)"
    draft_id = (await _draft_new(client, token, cards=[_card(body=body, todos=[])]))["draft"]["id"]
    stored = (await web.get(f"{DRAFTS}{draft_id}")).json()["cards"][0]["body"]
    assert f"user:{colleague.id}" not in stored and "file:1" not in stored
    assert "@Hans Müller" in stored


async def test_discarding_deletes_the_draft_and_writes_nothing(
    client: httpx.AsyncClient, web: httpx.AsyncClient, token: str
) -> None:
    project = await _project(web)
    draft_id = (await _draft_new(client, token))["draft"]["id"]
    assert (await web.delete(f"{DRAFTS}{draft_id}")).status_code == 204
    assert (await web.get(f"{DRAFTS}{draft_id}")).status_code == 404
    assert (await web.get(MEETINGS, params={"project_id": project["id"]})).json() == []


async def test_a_draft_needs_a_target_and_cards(
    client: httpx.AsyncClient, web: httpx.AsyncClient, token: str
) -> None:
    await _project(web)
    no_meeting = await call_tool(
        client,
        token,
        "draft_meeting_notes",
        {"project_number": "26-0142", "cards": [_card()]},
    )
    assert no_meeting["isError"] is True
    unknown = await call_tool(
        client,
        token,
        "draft_meeting_notes",
        {"project_number": "26-0142", "meeting_number": "MTG-X", "cards": [_card()]},
    )
    assert unknown["isError"] is True


async def test_the_draft_tool_needs_write_meetings(
    client: httpx.AsyncClient, db: AsyncSession, owner: User
) -> None:
    reading = await mint_agent_token(db, owner, [Permission.USE_MCP], name="reader")
    names = await list_tool_names(client, reading)
    assert "meetings" in names
    assert "draft_meeting_notes" not in names


async def test_drafts_past_their_retention_are_deleted(
    db: AsyncSession, web: httpx.AsyncClient, owner: User
) -> None:
    project = await _project(web)
    repo = SqlAlchemyMeetingNotesDraftRepository(db)

    def _draft(created: datetime) -> MeetingNotesDraft:
        return MeetingNotesDraft(
            id=0,
            creator_id=owner.id,
            created=created,
            meeting_id=None,
            project_id=project["id"],
            product_id=None,
            new_meeting=None,
            cards=[DraftCard(scope=None, scope_icon=None, body="x")],
        )

    old = await repo.save(_draft(datetime.now(UTC) - timedelta(days=31)))
    fresh = await repo.save(_draft(datetime.now(UTC) - timedelta(days=1)))
    await db.commit()

    removed = await PurgeExpiredMeetingNotesDrafts(repo, SqlAlchemyUnitOfWork(db)).execute()
    assert removed == 1
    assert await repo.get_by_id(old.id) is None
    assert await repo.get_by_id(fresh.id) is not None


async def test_a_repeated_idempotency_key_creates_no_second_draft(
    client: httpx.AsyncClient, web: httpx.AsyncClient, token: str
) -> None:
    await _project(web)
    first = await _draft_new(client, token, idempotency_key="notebook-1")
    again = await call_tool(
        client,
        token,
        "draft_meeting_notes",
        {
            "project_number": "26-0142",
            "new_meeting_name": "Kick-off cabinet",
            "new_meeting_starts_at": START.isoformat(),
            "cards": [_card()],
            "idempotency_key": "notebook-1",
        },
    )
    assert again["isError"] is False
    assert [d["id"] for d in (await web.get(DRAFTS)).json()] == [first["draft"]["id"]]
