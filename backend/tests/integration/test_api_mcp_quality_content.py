"""
The content tools of Quality on the MCP surface over HTTP: one flow
sequence step by step with its devices, positions and variants named, and
one saved calculation with its inputs and results. Products, devices,
sequences and calculations are created through the web API, and every
tool is called the way an agent client calls it.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.const import API_WEB
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration._mcp_helpers import call_tool
from tests.integration._mcp_helpers import mint_agent_token
from tests.integration._mcp_helpers import save_agent_settings
from tests.integration.conftest import auth_headers

RESOURCES = f"{API_WEB}/product-device-resources"
SEQUENCES = f"{API_WEB}/sequences"
CALCULATIONS = f"{API_WEB}/calculations"


@pytest.fixture(autouse=True)
async def agents_on(db: AsyncSession) -> None:
    await save_agent_settings(db)


@pytest.fixture
async def agent_owner(create_user: Callable[..., Awaitable[User]]) -> User:
    return await create_user(
        username="content-reader",
        email="content-reader@example.com",
        permissions=[
            Permission.WRITE_PAT,
            Permission.USE_MCP,
            Permission.WRITE_CALCULATIONS,
            Permission.RELEASE_CALCULATIONS,
        ],
    )


@pytest.fixture
async def token(db: AsyncSession, agent_owner: User) -> str:
    return await mint_agent_token(db, agent_owner, [Permission.USE_MCP])


@pytest.fixture
async def writer(auth_client: Any) -> httpx.AsyncClient:
    c: httpx.AsyncClient = await auth_client(
        username="sequence-writer",
        email="sequence-writer@example.com",
        permissions=[
            Permission.WRITE_PROJECTS,
            Permission.MANAGE_PROJECTS,
            Permission.WRITE_PRODUCT_DEVICE_RESOURCES,
            Permission.WRITE_SEQUENCES,
            Permission.RELEASE_SEQUENCES,
        ],
    )
    return c


async def _ok(response: httpx.Response, status: int = 200) -> Any:
    assert response.status_code == status, response.text
    return response.json()


def _text(result: dict[str, Any]) -> str:
    return str(result["content"][0]["text"])


async def _product(client: httpx.AsyncClient) -> dict[str, Any]:
    """A product with one linear drive, which starts retracted, and two
    variants."""
    product = await _ok(
        await client.post(f"{API_WEB}/products/", json={"product_number": "M26101"}), 201
    )
    medium = await _ok(
        await client.post(
            f"{RESOURCES}/options",
            json={"category": "driving_medium", "label": {"enGB": "Pneumatics"}, "letter": "P"},
        ),
        201,
    )
    kind = await _ok(
        await client.post(
            f"{RESOURCES}/kinds",
            json={
                "label": {"enGB": "Linear drive"},
                "positions": [
                    {"label": {"enGB": "Retracted"}},
                    {"label": {"enGB": "Extended"}},
                    {"label": {"enGB": "Intermediate"}, "takes_value": True, "unit": "mm"},
                ],
            },
        ),
        201,
    )
    retracted, extended, intermediate = (p["id"] for p in kind["positions"])
    device_body = {
        "location": "B01",
        "name": "Lift",
        "driving_medium_id": medium["id"],
        "kind_id": kind["id"],
        "initial_position_id": retracted,
    }
    device = await _ok(
        await client.post(f"{API_WEB}/products/{product['id']}/devices", json=device_body), 201
    )
    variants = await _ok(
        await client.put(
            f"{API_WEB}/products/{product['id']}/variants",
            json={"variants": [{"name": "Clamp 60"}, {"name": "Clamp 80"}]},
        )
    )
    return {
        "product": product,
        "device": device,
        "device_body": device_body,
        "variants": variants,
        "retracted": retracted,
        "extended": extended,
        "intermediate": intermediate,
    }


def _steps(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    device_id = ctx["device"]["id"]
    small, large = (str(v["id"]) for v in ctx["variants"])
    return [
        {
            "key": "s1",
            "actions": [
                {
                    "key": "a1",
                    "kind": "device",
                    "device_id": device_id,
                    "position_id": ctx["intermediate"],
                    "value": {"per_variant": {small: 60, large: 80}},
                }
            ],
            "transitions": [
                {
                    "key": "t1",
                    "condition": [
                        {
                            "kind": "device_position",
                            "device_id": device_id,
                            "position_id": ctx["intermediate"],
                        }
                    ],
                }
            ],
        },
        {
            "key": "s2",
            "timeout_ms": 2000,
            "actions": [
                {
                    "key": "a2",
                    "kind": "device",
                    "device_id": device_id,
                    "position_id": ctx["retracted"],
                },
                {"key": "a3", "kind": "text", "qualifier": "pulse", "text": "Count part"},
            ],
            "transitions": [
                {"key": "t2", "target": "s1", "condition": [{"kind": "external", "text": "Go"}]},
                {
                    "key": "t3",
                    "target": "end",
                    "condition": [{"kind": "time", "duration_ms": {"common": 500}}],
                },
            ],
        },
    ]


async def _sequence(client: httpx.AsyncClient, ctx: dict[str, Any]) -> dict[str, Any]:
    created = await _ok(
        await client.post(
            SEQUENCES, json={"product_id": ctx["product"]["id"], "name": "Automatic"}
        ),
        201,
    )
    await _ok(await client.post(f"{SEQUENCES}/{created['id']}/lock", json={}))
    saved: dict[str, Any] = await _ok(
        await client.put(
            f"{SEQUENCES}/{created['id']}", json={"name": "Automatic", "steps": _steps(ctx)}
        )
    )
    return saved


# ── sequence ──────────────────────────────────────────────────────────


async def test_sequence_reads_a_draft_step_by_step_with_names(
    client: httpx.AsyncClient, writer: httpx.AsyncClient, token: str
) -> None:
    ctx = await _product(writer)
    sequence = await _sequence(writer, ctx)

    result = await call_tool(
        client, token, "sequence", {"document_number": sequence["document_number"]}
    )

    assert result["isError"] is False, _text(result)
    data = result["structuredContent"]
    header = data["sequence"]
    assert header["name"] == "Automatic"
    assert header["status"] == "draft"
    assert header["names_frozen"] is False
    assert header["variants"] == ["Clamp 60", "Clamp 80"]
    # The writer's name stays out while the agent settings leave names out.
    assert header["creator_full_name"] == "[hidden]"
    lift = ctx["device"]["name_utf8"]
    [device] = data["devices"]
    assert device["name"] == lift
    assert device["kind"] == "Linear drive"
    assert device["initial_position"] == "Retracted"

    first, second = data["steps"]
    [move] = first["actions"]
    assert move["device"] == lift
    assert move["position"] == "Intermediate"
    assert move["unit"] == "mm"
    assert move["value"] == {"per_variant": {"Clamp 60": 60, "Clamp 80": 80}}
    assert first["transitions"] == [
        {
            "to_step": 2,
            "condition": [
                {
                    "kind": "device_position",
                    "device": lift,
                    "position": "Intermediate",
                    "unit": "mm",
                }
            ],
        }
    ]
    assert second["timeout_ms"] == 2000
    assert second["actions"][1] == {"kind": "text", "qualifier": "pulse", "text": "Count part"}
    assert [t["to_step"] for t in second["transitions"]] == [1, "end"]
    assert second["transitions"][1]["condition"] == [
        {"kind": "time", "duration_ms": {"common": 500}}
    ]
    assert [r["status"] for r in data["revisions"]] == ["draft"]


async def test_sequence_released_revision_keeps_the_frozen_names(
    client: httpx.AsyncClient, writer: httpx.AsyncClient, token: str
) -> None:
    ctx = await _product(writer)
    sequence = await _sequence(writer, ctx)
    released = await _ok(await writer.post(f"{SEQUENCES}/{sequence['id']}/release"))
    old_name = ctx["device"]["name_utf8"]
    renamed = await _ok(
        await writer.put(
            f"{API_WEB}/product-devices/{ctx['device']['id']}",
            json={
                **ctx["device_body"],
                "name": "Lifter",
                "expected_edit_version": ctx["device"]["edit_version"],
            },
        )
    )
    draft = await _ok(
        await writer.post(f"{SEQUENCES}/{sequence['id']}/revise", json={"reason": "Faster"}),
        201,
    )
    by_name = {"product_id": ctx["product"]["id"], "name": "automatic"}

    old = await call_tool(client, token, "sequence", {**by_name, "revision": released["revision"]})
    latest = await call_tool(client, token, "sequence", by_name)

    assert old["isError"] is False, _text(old)
    old_data = old["structuredContent"]
    assert old_data["sequence"]["status"] == "released"
    assert old_data["sequence"]["names_frozen"] is True
    assert old_data["steps"][0]["actions"][0]["device"] == old_name
    assert latest["isError"] is False, _text(latest)
    latest_data = latest["structuredContent"]
    assert latest_data["sequence"]["revision"] == draft["revision"]
    assert latest_data["sequence"]["names_frozen"] is False
    assert latest_data["steps"][0]["actions"][0]["device"] == renamed["name_utf8"]
    assert [r["revision"] for r in latest_data["revisions"]] == [
        draft["revision"],
        released["revision"],
    ]


async def test_sequence_refuses_two_ways_to_name_it_and_an_unknown_one(
    client: httpx.AsyncClient, writer: httpx.AsyncClient, token: str
) -> None:
    ctx = await _product(writer)
    sequence = await _sequence(writer, ctx)

    both = await call_tool(
        client,
        token,
        "sequence",
        {"document_number": sequence["document_number"], "public_id": sequence["public_id"]},
    )
    unknown = await call_tool(client, token, "sequence", {"document_number": "SEQ-404"})
    no_revision = await call_tool(
        client,
        token,
        "sequence",
        {"public_id": sequence["public_id"], "revision": "Z"},
    )

    assert both["isError"] is True
    assert "once" in _text(both)
    assert unknown["isError"] is True
    assert "SEQ-404" in _text(unknown)
    assert no_revision["isError"] is True
    assert "no revision Z" in _text(no_revision)


# ── calculation ───────────────────────────────────────────────────────


def _calculation(**overrides: Any) -> dict[str, Any]:
    return {
        "tool": "drive_sizing",
        "title": "Vertical axis, 140 kg",
        "note": "Belt drive",
        "inputs": {"orientation": "vertical", "mass_kg": 140},
        "results": {"torque_nm": 12.5},
        "input_version": 1,
        "engine_version": 3,
    } | overrides


async def _created(client: httpx.AsyncClient, user: User, body: dict[str, Any]) -> dict[str, Any]:
    response = await client.post(CALCULATIONS, json=body, headers=await auth_headers(user))
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


async def test_calculation_reads_inputs_results_and_revisions_by_document_number(
    client: httpx.AsyncClient, agent_owner: User, token: str
) -> None:
    calculation = await _created(client, agent_owner, _calculation())
    headers = await auth_headers(agent_owner)
    await _ok(await client.post(f"{CALCULATIONS}/{calculation['id']}/release", headers=headers))
    revision = await _ok(
        await client.post(
            f"{CALCULATIONS}/{calculation['id']}/revise",
            json={"reason": "New gearbox"},
            headers=headers,
        ),
        201,
    )
    number = calculation["document_number"]

    latest = await call_tool(client, token, "calculation", {"document_number": number.lower()})
    released = await call_tool(
        client,
        token,
        "calculation",
        {"document_number": number, "revision": calculation["revision"], "include_inputs": False},
    )

    assert latest["isError"] is False, _text(latest)
    data = latest["structuredContent"]
    assert data["calculation"]["revision"] == revision["revision"]
    assert data["calculation"]["status"] == "draft"
    assert data["calculation"]["tool"] == "drive_sizing"
    assert data["calculation"]["owner"] == "personal"
    assert data["calculation"]["engine_version"] == 3
    assert data["inputs"] == {"orientation": "vertical", "mass_kg": 140}
    assert data["results"] == {"torque_nm": 12.5}
    assert [r["revision"] for r in data["revisions"]] == [
        revision["revision"],
        calculation["revision"],
    ]
    assert released["isError"] is False, _text(released)
    old = released["structuredContent"]
    assert old["calculation"]["status"] == "released"
    assert "inputs" not in old
    assert old["results"] == {"torque_nm": 12.5}


async def test_calculation_does_not_find_another_users_personal_calculation(
    client: httpx.AsyncClient,
    create_user: Callable[..., Awaitable[User]],
    token: str,
) -> None:
    colleague = await create_user(
        username="content-colleague",
        email="content-colleague@example.com",
        permissions=[Permission.WRITE_CALCULATIONS],
    )
    theirs = await _created(client, colleague, _calculation(title="Colleague's own"))

    by_number = await call_tool(
        client, token, "calculation", {"document_number": theirs["document_number"]}
    )
    by_public_id = await call_tool(client, token, "calculation", {"public_id": theirs["public_id"]})

    assert by_number["isError"] is True
    assert theirs["document_number"] in _text(by_number)
    assert by_public_id["isError"] is True
