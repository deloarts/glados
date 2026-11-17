"""
The state machine catalogue endpoint over real HTTP: any authenticated user
(no special permission) can read it, and its shape and content match the
domain catalogue built from the live derivation and intent tables.
"""

from src.read.domain.services.state_machine_catalog import STATE_MACHINE_REGISTRY
from src.read.domain.services.state_machine_catalog import build_state_machine_catalog

_PATH = "/api/v1/web/state-machines/"


async def test_requires_authentication(client):
    response = await client.get(_PATH)

    assert response.status_code == 401


async def test_any_authenticated_user_can_read_it(auth_client):
    reader = await auth_client(permissions=[])

    response = await reader.get(_PATH)

    assert response.status_code == 200


async def test_response_matches_the_live_domain_catalogue_exactly(auth_client):
    reader = await auth_client(permissions=[])

    body = (await reader.get(_PATH)).json()

    expected = build_state_machine_catalog()
    assert [m["key"] for m in body["machines"]] == [g.key for g in expected]
    for machine, graph in zip(body["machines"], expected, strict=True):
        assert machine["entity"] == graph.entity
        assert machine["kind"] == graph.kind.value
        assert machine["description"] == graph.description
        assert machine["states"] == [
            {"value": s.value, "initial": s.initial, "terminal": s.terminal} for s in graph.states
        ]
        assert machine["edges"] == [
            {"from_state": e.from_state, "to_state": e.to_state} for e in graph.edges
        ]
        assert machine["rules"] == [
            {
                "number": r.number,
                "text_key": r.text_key,
                "condition": r.condition,
                "result": r.result,
                "results": list(r.results),
                "result_text_key": r.result_text_key,
            }
            for r in graph.rules
        ]
        assert machine["intents"] == [
            {
                "action": i.action,
                "text_key": i.text_key,
                "allowed_from": list(i.allowed_from) if i.allowed_from is not None else None,
                "condition": i.condition,
                "permission": i.permission,
                "effect": i.effect,
                "target": i.target,
            }
            for i in graph.intents
        ]


async def test_edges_use_from_state_to_state_field_names_not_from(auth_client):
    """`from` is a reserved word in Python and many clients; edges are keyed
    from_state and to_state."""
    reader = await auth_client(permissions=[])

    body = (await reader.get(_PATH)).json()

    catalogue_item = next(m for m in body["machines"] if m["key"] == "catalogue_item_status")
    assert len(catalogue_item["edges"]) > 0
    for edge in catalogue_item["edges"]:
        assert set(edge.keys()) == {"from_state", "to_state"}


async def test_registry_order_is_the_response_order(auth_client):
    reader = await auth_client(permissions=[])

    body = (await reader.get(_PATH)).json()

    assert [m["key"] for m in body["machines"]] == [e.key for e in STATE_MACHINE_REGISTRY]


async def test_the_lot_machine_lists_its_derivation_rows_and_actions(auth_client):
    reader = await auth_client(permissions=[])

    body = (await reader.get(_PATH)).json()

    lot_machine = next(m for m in body["machines"] if m["key"] == "lot_status")
    assert lot_machine["entity"] == "Lot"
    assert lot_machine["kind"] == "derived"
    assert lot_machine["edges"] == []
    assert {s["value"] for s in lot_machine["states"]} == {
        "draft",
        "partially_planned",
        "planned",
        "in_progress",
        "on_hold",
        "completed",
        "canceled",
        "scrapped",
    }
    assert {s["value"] for s in lot_machine["states"] if s["terminal"]} == {
        "completed",
        "canceled",
        "scrapped",
    }
    assert [s["value"] for s in lot_machine["states"] if s["initial"]] == ["draft"]
    assert [r["results"] for r in lot_machine["rules"]][:3] == [
        ["canceled"],
        ["scrapped"],
        ["completed"],
    ]
    assert lot_machine["rules"][-1]["condition"] == "otherwise"
    actions = {i["action"]: i for i in lot_machine["intents"]}
    assert actions["hold"]["allowed_from"] == ["partially_planned", "planned", "in_progress"]
    assert actions["force_complete"]["permission"] == "manage:lots"
