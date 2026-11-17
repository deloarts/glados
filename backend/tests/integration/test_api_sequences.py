"""
Flow sequences over HTTP: creating one on a product with steps that name
its devices, positions and variants, the edit lock, the release that
freezes the names, revisions, and the refusals for content that does not
fit the product. Every write is read back through a separate request, so a
missing commit fails here.
"""

from typing import Any

import httpx
import pytest

from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission

URL = f"{API_WEB}/sequences"
RESOURCES = f"{API_WEB}/product-device-resources"
PERMISSIONS = [
    Permission.WRITE_PROJECTS,
    Permission.MANAGE_PROJECTS,
    Permission.WRITE_PRODUCT_DEVICE_RESOURCES,
    Permission.WRITE_SEQUENCES,
    Permission.RELEASE_SEQUENCES,
]


@pytest.fixture
async def writer(auth_client: Any) -> httpx.AsyncClient:
    c: httpx.AsyncClient = await auth_client(permissions=PERMISSIONS)
    return c


async def _ok(response: httpx.Response, status: int = 200) -> Any:
    assert response.status_code == status, response.text
    return response.json()


async def _setup(client: httpx.AsyncClient) -> dict[str, Any]:
    product = await _ok(
        await client.post(f"{API_WEB}/products/", json={"product_number": "M26001"}), 201
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
    device = await _ok(
        await client.post(
            f"{API_WEB}/products/{product['id']}/devices",
            json={
                "location": "B01",
                "name": "Lift",
                "driving_medium_id": medium["id"],
                "kind_id": kind["id"],
            },
        ),
        201,
    )
    variants = await _ok(
        await client.put(
            f"{API_WEB}/products/{product['id']}/variants",
            json={"variants": [{"name": "Clamp 60"}, {"name": "Clamp 80"}]},
        )
    )
    retracted, extended, intermediate = (p["id"] for p in kind["positions"])
    return {
        "product": product,
        "device": device,
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
                {
                    "key": "t2",
                    "target": "s1",
                    "condition": [{"kind": "external", "text": "Start"}],
                },
                {
                    "key": "t3",
                    "target": "end",
                    "condition": [{"kind": "time", "duration_ms": {"common": 500}}],
                },
            ],
        },
    ]


async def test_sequence_lifecycle_freezes_names_on_release(writer: httpx.AsyncClient) -> None:
    ctx = await _setup(writer)
    product_id = ctx["product"]["id"]
    created = await _ok(
        await writer.post(URL, json={"product_id": product_id, "name": "  Automatic  "}), 201
    )
    assert created["name"] == "Automatic"
    assert created["document_number"].startswith("SEQ-")
    assert created["steps"] == []

    body = {"name": "Automatic", "steps": _steps(ctx)}
    unlocked = await writer.put(f"{URL}/{created['id']}", json=body)
    assert unlocked.status_code == 409
    await _ok(await writer.post(f"{URL}/{created['id']}/lock", json={}))
    await _ok(await writer.put(f"{URL}/{created['id']}", json=body))

    read = await _ok(await writer.get(f"{URL}/{created['id']}"))
    assert [s["key"] for s in read["steps"]] == ["s1", "s2"]
    assert read["steps"][1]["actions"][1]["qualifier"] == "pulse"
    assert read["frozen"] is None
    listed = await _ok(await writer.get(URL, params={"product_id": product_id}))
    assert [(i["name"], i["step_count"]) for i in listed["items"]] == [("Automatic", 2)]
    # The list names who saved the last change, beside when.
    item = listed["items"][0]
    assert item["changed_by_id"] == created["creator_id"]
    assert item["changed_by_full_name"] == created["creator_full_name"]

    released = await _ok(await writer.post(f"{URL}/{created['id']}/release"))
    device = released["frozen"]["devices"][str(ctx["device"]["id"])]
    assert device["name"] == ctx["device"]["name_utf8"]
    assert device["positions"][str(ctx["extended"])]["label"] == {"enGB": "Extended"}
    assert list(released["frozen"]["variants"].values()) == ["Clamp 60", "Clamp 80"]

    readonly = await writer.put(f"{URL}/{created['id']}", json=body)
    assert readonly.status_code == 409
    assert readonly.json()["code"] == "SequenceReleasedError"

    revision = await _ok(
        await writer.post(f"{URL}/{created['id']}/revise", json={"reason": "Faster"}), 201
    )
    assert revision["revision"] != released["revision"]
    assert revision["steps"] == released["steps"]
    assert revision["frozen"] is None
    revisions = await _ok(await writer.get(f"{URL}/{revision['id']}/revisions"))
    assert [r["id"] for r in revisions] == [revision["id"], created["id"]]


@pytest.mark.parametrize(
    "broken",
    [
        # A device action needs a position of the device's kind.
        lambda ctx, steps: steps[0]["actions"][0].update(position_id=999999),
        # A position that takes a value needs one for every variant.
        lambda ctx, steps: steps[0]["actions"][0].update(value={"per_variant": {}}),
        # Alternative transitions each need a condition.
        lambda ctx, steps: steps[1]["transitions"][0].update(condition=[]),
        # A transition leads to a step of this sequence.
        lambda ctx, steps: steps[1]["transitions"][0].update(target="nowhere"),
        # Keys are unique.
        lambda ctx, steps: steps[1].update(key="s1"),
    ],
)
async def test_sequence_rejects_content_that_does_not_fit(
    writer: httpx.AsyncClient, broken: Any
) -> None:
    ctx = await _setup(writer)
    steps = _steps(ctx)
    broken(ctx, steps)
    r = await writer.post(
        URL, json={"product_id": ctx["product"]["id"], "name": "Automatic", "steps": steps}
    )
    assert r.status_code == 422, r.text


async def test_sequence_draft_keeps_an_archived_device_but_release_refuses(
    writer: httpx.AsyncClient,
) -> None:
    ctx = await _setup(writer)
    created = await _ok(
        await writer.post(
            URL,
            json={"product_id": ctx["product"]["id"], "name": "Homing", "steps": _steps(ctx)},
        ),
        201,
    )
    await _ok(await writer.post(f"{API_WEB}/product-devices/{ctx['device']['id']}/archive"))
    await _ok(await writer.post(f"{URL}/{created['id']}/lock", json={}))
    await _ok(
        await writer.put(f"{URL}/{created['id']}", json={"name": "Homing", "steps": _steps(ctx)})
    )
    refused = await writer.post(f"{URL}/{created['id']}/release")
    assert refused.status_code == 422
    assert refused.json()["code"] == "SequenceInvalidError"


async def test_sequence_create_needs_permission(
    writer: httpx.AsyncClient, auth_client: Any
) -> None:
    ctx = await _setup(writer)
    reader = await auth_client(permissions=[], username="reader", email="reader@example.com")
    r = await reader.post(URL, json={"product_id": ctx["product"]["id"], "name": "Automatic"})
    assert r.status_code == 403
    assert (await reader.get(URL)).status_code == 200
