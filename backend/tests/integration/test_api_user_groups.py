"""
User groups through the API with the real repositories: a member holds the
group's permissions on top of their own and loses them on leaving or when
the group is deleted, membership is set from either side, every signed-in
user reads the groups, only write:settings changes them, nobody raises
their own permissions through a group, and only users whose effective
permissions changed are told.
"""

from collections.abc import AsyncIterator
from collections.abc import Awaitable
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from src.modules.platform.const import API_WEB
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.events.user_events import UserPermissionsChanged
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration.conftest import _new_client
from tests.integration.conftest import auth_headers

GROUPS = f"{API_WEB}/user-groups"
USERS = f"{API_WEB}/users"
HOLIDAYS = f"{API_WEB}/holidays"
SHUTDOWN = {
    "name": "Summer shutdown",
    "category": "plant_shutdown",
    "start_date": "2026-08-03",
    "end_date": "2026-08-14",
}

ClientFor = Callable[[User], Awaitable[httpx.AsyncClient]]
CreateUser = Callable[..., Awaitable[User]]


@pytest.fixture
async def client_for() -> AsyncIterator[ClientFor]:
    clients: list[httpx.AsyncClient] = []

    async def _client(user: User) -> httpx.AsyncClient:
        c = _new_client()
        c.headers.update(await auth_headers(user))
        clients.append(c)
        return c

    yield _client
    for c in clients:
        await c.aclose()


async def _person(create_user: CreateUser, name: str, permissions: list[str] | None = None) -> User:
    return await create_user(username=name, email=f"{name}@example.com", permissions=permissions)


async def _admin(create_user: CreateUser, client_for: ClientFor) -> httpx.AsyncClient:
    return await client_for(await _person(create_user, "admin", [Permission.WRITE_SETTINGS]))


async def _create_group(admin: httpx.AsyncClient, **body: Any) -> dict[str, Any]:
    response = await admin.post(GROUPS, json={"name": "Planning", **body})
    assert response.status_code == 201, response.text
    return dict(response.json())


async def _me(client: httpx.AsyncClient) -> dict[str, Any]:
    response = await client.get(f"{USERS}/me")
    assert response.status_code == 200, response.text
    return dict(response.json())


async def test_a_member_holds_the_group_permissions_until_they_leave(
    create_user: CreateUser, client_for: ClientFor
) -> None:
    admin = await _admin(create_user, client_for)
    planner = await _person(create_user, "planner")
    planner_client = await client_for(planner)
    assert (await planner_client.post(HOLIDAYS, json=SHUTDOWN)).status_code == 403

    group = await _create_group(
        admin, permissions=[Permission.WRITE_MACHINES], member_ids=[planner.id]
    )

    me = await _me(planner_client)
    assert me["permissions"] == [Permission.WRITE_MACHINES]
    assert me["direct_permissions"] == []
    assert me["group_ids"] == [group["id"]]
    assert (await planner_client.post(HOLIDAYS, json=SHUTDOWN)).status_code == 201

    left = await admin.put(f"{GROUPS}/{group['id']}", json={"name": "Planning", "member_ids": []})
    assert left.status_code == 200, left.text
    assert (await planner_client.post(HOLIDAYS, json=SHUTDOWN)).status_code == 403
    assert (await _me(planner_client))["group_ids"] == []


async def test_membership_set_from_the_user_side_shows_on_the_group(
    create_user: CreateUser, client_for: ClientFor
) -> None:
    admin = await _admin(create_user, client_for)
    planner = await _person(create_user, "planner")
    group = await _create_group(admin, permissions=[Permission.WRITE_MACHINES])

    updated = await admin.put(f"{USERS}/{planner.id}", json={"group_ids": [group["id"]]})

    assert updated.status_code == 200, updated.text
    assert updated.json()["group_ids"] == [group["id"]]
    assert updated.json()["permissions"] == [Permission.WRITE_MACHINES]
    listed = (await admin.get(GROUPS)).json()
    assert [(g["id"], g["member_ids"]) for g in listed] == [(group["id"], [planner.id])]


async def test_deleting_a_group_takes_its_permissions_and_tells_only_who_lost_some(
    create_user: CreateUser, client_for: ClientFor, published_events: list[object]
) -> None:
    admin = await _admin(create_user, client_for)
    planner = await _person(create_user, "planner")
    also_direct = await _person(create_user, "direct", [Permission.WRITE_MACHINES])
    group = await _create_group(
        admin, permissions=[Permission.WRITE_MACHINES], member_ids=[planner.id, also_direct.id]
    )
    published_events.clear()

    deleted = await admin.delete(f"{GROUPS}/{group['id']}")

    assert deleted.status_code == 204, deleted.text
    assert (await admin.get(GROUPS)).json() == []
    assert (await _me(await client_for(planner)))["permissions"] == []
    assert (await _me(await client_for(also_direct)))["permissions"] == [Permission.WRITE_MACHINES]
    notified = [e.user_id for e in published_events if isinstance(e, UserPermissionsChanged)]
    assert notified == [planner.id]


async def test_every_user_reads_the_groups_but_only_write_settings_changes_them(
    create_user: CreateUser, client_for: ClientFor
) -> None:
    admin = await _admin(create_user, client_for)
    group = await _create_group(admin)
    reader = await client_for(await _person(create_user, "reader"))

    assert [g["id"] for g in (await reader.get(GROUPS)).json()] == [group["id"]]
    assert (await reader.post(GROUPS, json={"name": "Mine"})).status_code == 403
    assert (await reader.delete(f"{GROUPS}/{group['id']}")).status_code == 403


async def test_nobody_raises_their_own_permissions_through_a_group(
    create_user: CreateUser, client_for: ClientFor
) -> None:
    admin_user = await _person(create_user, "admin", [Permission.WRITE_SETTINGS])
    admin = await client_for(admin_user)
    other_admin = await client_for(await _person(create_user, "other", [Permission.WRITE_SETTINGS]))

    joined_self = await admin.post(GROUPS, json={"name": "Mine", "member_ids": [admin_user.id]})
    assert joined_self.status_code == 403, joined_self.text

    group = await _create_group(other_admin, member_ids=[admin_user.id])
    raised = await admin.put(
        f"{GROUPS}/{group['id']}",
        json={
            "name": "Planning",
            "permissions": [Permission.WRITE_MACHINES],
            "member_ids": [admin_user.id],
        },
    )
    assert raised.status_code == 403, raised.text

    renamed = await admin.put(
        f"{GROUPS}/{group['id']}", json={"name": "Renamed", "member_ids": [admin_user.id]}
    )
    assert renamed.status_code == 200, renamed.text

    # The own-account update round-trips group_ids but cannot change them.
    own = await admin.put(f"{USERS}/{admin_user.id}", json={"group_ids": []})
    assert own.status_code == 200, own.text
    assert own.json()["group_ids"] == [group["id"]]


async def test_bad_groups_are_refused(create_user: CreateUser, client_for: ClientFor) -> None:
    admin = await _admin(create_user, client_for)
    service = await create_user(username="svc", email="svc@example.com", is_service_account=True)
    await _create_group(admin, name="Planning")

    duplicate = await admin.post(GROUPS, json={"name": "planning"})
    terminal = await admin.post(
        GROUPS, json={"name": "Screens", "permissions": [Permission.CONNECT_TERMINALS]}
    )
    service_member = await admin.post(GROUPS, json={"name": "Bots", "member_ids": [service.id]})
    unknown_group = await admin.put(f"{USERS}/{service.id}", json={"group_ids": [999]})

    assert duplicate.status_code == 409, duplicate.text
    assert terminal.status_code == 422, terminal.text
    assert service_member.status_code == 422, service_member.text
    assert unknown_group.status_code == 422, unknown_group.text
    assert [g["name"] for g in (await admin.get(GROUPS)).json()] == ["Planning"]
