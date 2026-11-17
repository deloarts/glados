"""
Product devices and the lists they pick from, over HTTP: the resource
lists with their letter and label rules, device names and numbers with both
uniqueness constraints, archived devices keeping their names, components
with EPLAN tags, and the name preview. Every write is read back through a
separate request, so a missing commit fails here.
"""

from typing import Any

import httpx
import pytest

from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration._edit_versions import row_version

RESOURCES = f"{API_WEB}/product-device-resources"
PERMISSIONS = [
    Permission.WRITE_PROJECTS,
    Permission.MANAGE_PROJECTS,
    Permission.WRITE_PRODUCT_DEVICE_RESOURCES,
    Permission.WRITE_CALCULATIONS,
    Permission.RELEASE_CALCULATIONS,
]


@pytest.fixture
async def writer(auth_client: Any) -> httpx.AsyncClient:
    c: httpx.AsyncClient = await auth_client(permissions=PERMISSIONS)
    return c


async def _option(
    client: httpx.AsyncClient, category: str, label: str, letter: str | None = None
) -> dict[str, Any]:
    body: dict[str, Any] = {"category": category, "label": {"enGB": label}}
    if letter is not None:
        body["letter"] = letter
    r = await client.post(f"{RESOURCES}/options", json=body)
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


async def _kind(client: httpx.AsyncClient) -> dict[str, Any]:
    r = await client.post(
        f"{RESOURCES}/kinds",
        json={
            "label": {"enGB": "Linear drive", "deAT": "Linearantrieb"},
            "positions": [
                {"label": {"enGB": "Retracted"}},
                {"label": {"enGB": "Extended"}},
                {"label": {"enGB": "Intermediate"}, "takes_value": True, "unit": "mm"},
            ],
            "parameters": [{"label": {"enGB": "Bore"}, "unit": "mm"}],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


async def _product(client: httpx.AsyncClient, number: str = "M26001") -> dict[str, Any]:
    r = await client.post(f"{API_WEB}/products/", json={"product_number": number})
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


async def _setup(client: httpx.AsyncClient) -> dict[str, Any]:
    return {
        "product": await _product(client),
        "medium": await _option(client, "driving_medium", "Pneumatics", "P"),
        "role": await _option(client, "component_role", "Sensor"),
        "behaviour": await _option(client, "energy_behaviour", "Holds position"),
        "kind": await _kind(client),
    }


def _device_body(ctx: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "location": "B01-W4-L",
        "name": "Hubzylinder Einförderung",
        "driving_medium_id": ctx["medium"]["id"],
        "kind_id": ctx["kind"]["id"],
    }
    body.update(overrides)
    return body


async def _create_device(client: httpx.AsyncClient, ctx: dict[str, Any], **kw: Any) -> Any:
    return await client.post(
        f"{API_WEB}/products/{ctx['product']['id']}/devices", json=_device_body(ctx, **kw)
    )


# ── Resources ─────────────────────────────────────────────────────────


async def test_product_device_resources_need_permission(auth_client: Any) -> None:
    plain = await auth_client(permissions=[])
    r = await plain.post(
        f"{RESOURCES}/options",
        json={"category": "component_role", "label": {"enGB": "Valve"}},
    )
    assert r.status_code == 403


async def test_product_device_resources_label_needs_default_language(
    writer: httpx.AsyncClient,
) -> None:
    r = await writer.post(
        f"{RESOURCES}/options", json={"category": "component_role", "label": {"deAT": "Ventil"}}
    )
    assert r.status_code == 422
    assert r.json()["code"] == "LocalizedTextInvalidError"


async def test_product_device_resources_letter_rules(writer: httpx.AsyncClient) -> None:
    await _option(writer, "driving_medium", "Pneumatics", "P")

    duplicate = await writer.post(
        f"{RESOURCES}/options",
        json={"category": "driving_medium", "label": {"enGB": "Pressure"}, "letter": "P"},
    )
    assert duplicate.status_code == 409

    missing = await writer.post(
        f"{RESOURCES}/options", json={"category": "driving_medium", "label": {"enGB": "Air"}}
    )
    assert missing.status_code == 422

    listed = await writer.get(f"{RESOURCES}/options", params={"category": "driving_medium"})
    assert [o["letter"] for o in listed.json()] == ["P"]


async def test_product_device_resources_kind_edit_archives_removed_position(
    writer: httpx.AsyncClient,
) -> None:
    kind = await _kind(writer)
    kept, _removed, intermediate = kind["positions"]

    r = await writer.put(
        f"{RESOURCES}/kinds/{kind['id']}",
        json={
            "label": {"enGB": "Linear drive"},
            "positions": [
                {"id": intermediate["id"], "label": {"enGB": "Intermediate"}, "takes_value": True},
                {"id": kept["id"], "label": {"enGB": "Retracted"}},
            ],
            "parameters": [],
        },
    )
    assert r.status_code == 200, r.text

    fetched = (await writer.get(f"{RESOURCES}/kinds")).json()[0]
    live = [p["label"]["enGB"] for p in fetched["positions"] if not p["archived"]]
    archived = [p["label"]["enGB"] for p in fetched["positions"] if p["archived"]]
    assert live == ["Intermediate", "Retracted"]
    assert archived == ["Extended"]
    assert all(p["archived"] for p in fetched["parameters"])


async def test_product_device_resources_move_option_and_kind(writer: httpx.AsyncClient) -> None:
    sensor = await _option(writer, "component_role", "Sensor")
    valve = await _option(writer, "component_role", "Valve")
    await _option(writer, "energy_behaviour", "Holds position")

    r = await writer.post(f"{RESOURCES}/options/{valve['id']}/move", json={"direction": "up"})
    assert r.status_code == 200, r.text
    assert [o["id"] for o in r.json()] == [valve["id"], sensor["id"]]

    listed = await writer.get(f"{RESOURCES}/options", params={"category": "component_role"})
    assert [o["id"] for o in listed.json()] == [valve["id"], sensor["id"]]

    first = await _kind(writer)
    second = await _kind(writer)
    r = await writer.post(f"{RESOURCES}/kinds/{first['id']}/move", json={"direction": "down"})
    assert r.status_code == 200, r.text
    listed = await writer.get(f"{RESOURCES}/kinds")
    assert [k["id"] for k in listed.json()] == [second["id"], first["id"]]


async def test_product_device_resources_move_needs_write_permission(auth_client: Any) -> None:
    writer = await auth_client(permissions=PERMISSIONS)
    option = await _option(writer, "component_role", "Sensor")
    reader = await auth_client(permissions=[], username="reader", email="reader@example.com")
    r = await reader.post(f"{RESOURCES}/options/{option['id']}/move", json={"direction": "up"})
    assert r.status_code == 403


async def test_product_device_resources_place_option_and_kind(writer: httpx.AsyncClient) -> None:
    sensor = await _option(writer, "component_role", "Sensor")
    valve = await _option(writer, "component_role", "Valve")
    clamp = await _option(writer, "component_role", "Clamp")
    holds = await _option(writer, "energy_behaviour", "Holds position")

    r = await writer.post(
        f"{RESOURCES}/options/{clamp['id']}/place", json={"before_id": sensor["id"]}
    )
    assert r.status_code == 200, r.text
    assert [o["id"] for o in r.json()] == [clamp["id"], sensor["id"], valve["id"]]

    # A neighbour of another category is not part of this list.
    r = await writer.post(
        f"{RESOURCES}/options/{clamp['id']}/place", json={"after_id": holds["id"]}
    )
    assert r.status_code == 404

    first = await _kind(writer)
    second = await _kind(writer)
    third = await _kind(writer)
    r = await writer.post(f"{RESOURCES}/kinds/{first['id']}/place", json={"after_id": third["id"]})
    assert r.status_code == 200, r.text
    listed = await writer.get(f"{RESOURCES}/kinds")
    assert [k["id"] for k in listed.json()] == [second["id"], third["id"], first["id"]]


async def test_product_device_resources_place_needs_write_permission(auth_client: Any) -> None:
    writer = await auth_client(permissions=PERMISSIONS)
    option = await _option(writer, "component_role", "Sensor")
    reader = await auth_client(permissions=[], username="reader", email="reader@example.com")
    r = await reader.post(f"{RESOURCES}/options/{option['id']}/place", json={})
    assert r.status_code == 403


# ── Devices ───────────────────────────────────────────────────────────


@pytest.mark.smoke
async def test_product_devices_create_names_and_numbers(writer: httpx.AsyncClient) -> None:
    ctx = await _setup(writer)

    first = await _create_device(writer, ctx)
    assert first.status_code == 201, first.text
    second = await _create_device(writer, ctx)
    assert second.status_code == 201, second.text

    listed = await writer.get(f"{API_WEB}/products/{ctx['product']['id']}/devices")
    devices = listed.json()
    assert [d["name_utf8"] for d in devices] == [
        "B01-W4-L Hubzylinder Einförderung P1",
        "B01-W4-L Hubzylinder Einförderung P2",
    ]
    assert devices[0]["name_ascii"] == "B01_W4_L_Hubzylinder_Einfoerderung_P1"
    assert devices[0]["full_name_utf8"] == "M26001 B01-W4-L Hubzylinder Einförderung P1"
    assert devices[0]["full_name_ascii"] == "M26001_B01_W4_L_Hubzylinder_Einfoerderung_P1"


async def test_product_devices_ascii_collision_is_refused(writer: httpx.AsyncClient) -> None:
    ctx = await _setup(writer)
    assert (await _create_device(writer, ctx)).status_code == 201

    collision = await _create_device(writer, ctx, name="hubzylinder einfoerderung", number=1)
    assert collision.status_code == 409
    assert collision.json()["code"] == "ProductDeviceNameTakenError"

    # The transliterated spelling shares the numbering, so it gets the next number.
    next_free = await _create_device(writer, ctx, name="Hubzylinder Einfoerderung")
    assert next_free.status_code == 201
    assert next_free.json()["number"] == 2


async def test_product_devices_same_name_in_two_products(writer: httpx.AsyncClient) -> None:
    ctx = await _setup(writer)
    other = await _product(writer, "M26002")
    assert (await _create_device(writer, ctx)).status_code == 201
    r = await writer.post(f"{API_WEB}/products/{other['id']}/devices", json=_device_body(ctx))
    assert r.status_code == 201
    assert r.json()["number"] == 1


async def test_product_devices_archived_device_keeps_its_number(
    writer: httpx.AsyncClient,
) -> None:
    ctx = await _setup(writer)
    device = (await _create_device(writer, ctx)).json()
    archived = await writer.post(f"{API_WEB}/product-devices/{device['id']}/archive")
    assert archived.status_code == 200

    again = await _create_device(writer, ctx)
    assert again.status_code == 201
    assert again.json()["number"] == 2

    live = await writer.get(f"{API_WEB}/products/{ctx['product']['id']}/devices")
    assert [d["number"] for d in live.json()] == [2]


async def test_product_devices_invalid_characters_are_refused(writer: httpx.AsyncClient) -> None:
    ctx = await _setup(writer)
    r = await _create_device(writer, ctx, name="Zylinder 1/2")
    assert r.status_code == 422
    assert r.json()["code"] == "ProductDeviceNameInvalidError"


async def test_product_devices_letter_frozen_once_used(writer: httpx.AsyncClient) -> None:
    ctx = await _setup(writer)
    assert (await _create_device(writer, ctx)).status_code == 201

    r = await writer.put(
        f"{RESOURCES}/options/{ctx['medium']['id']}",
        json={"label": {"enGB": "Pneumatics"}, "letter": "PN"},
    )
    assert r.status_code == 409
    assert r.json()["code"] == "ProductDeviceLetterFrozenError"


async def test_product_devices_travel_times_round_trip_and_refuse_a_foreign_position(
    writer: httpx.AsyncClient,
) -> None:
    ctx = await _setup(writer)
    retracted, extended, _intermediate = ctx["kind"]["positions"]
    times = {str(retracted["id"]): 300, str(extended["id"]): 450}

    created = await _create_device(writer, ctx, travel_times_ms=times)
    assert created.status_code == 201, created.text
    fetched = (await writer.get(f"{API_WEB}/product-devices/{created.json()['id']}")).json()
    assert fetched["travel_times_ms"] == times

    refused = await _create_device(writer, ctx, name="Clamp", travel_times_ms={"999999": 300})
    assert refused.status_code == 422
    assert refused.json()["code"] == "ProductDeviceReferenceInvalidError"


async def test_product_devices_plc_data_and_components_round_trip(
    writer: httpx.AsyncClient,
) -> None:
    ctx = await _setup(writer)
    retracted, _extended, intermediate = ctx["kind"]["positions"]
    bore = ctx["kind"]["parameters"][0]

    created = await _create_device(
        writer,
        ctx,
        initial_position_id=intermediate["id"],
        initial_position_value=47,
        energy_loss_behaviour_id=ctx["behaviour"]["id"],
        energy_restoration_behaviour_id=ctx["behaviour"]["id"],
        monitoring_time_ms=1500,
        safety_relevant=True,
        parameters={str(bore["id"]): 32},
        position_labels={str(retracted["id"]): "up"},
        marker_x=0.25,
        marker_y=0.5,
        components=[
            {
                "role_id": ctx["role"]["id"],
                "eplan_tag": "-BG1",
                "b10d_cycles": 20000000,
                "signals": [
                    {
                        "signal_type": "di",
                        "meaning": "retracted",
                        "confirms_position_id": retracted["id"],
                        "safety": True,
                        "address": " I150.0 ",
                    }
                ],
            }
        ],
    )
    assert created.status_code == 201, created.text
    device_id = created.json()["id"]

    fetched = (await writer.get(f"{API_WEB}/product-devices/{device_id}")).json()
    assert fetched["initial_position_value"] == 47
    assert fetched["parameters"] == {str(bore["id"]): 32}
    assert fetched["position_labels"] == {str(retracted["id"]): "up"}
    assert fetched["safety_relevant"] is True
    component = fetched["components"][0]
    assert component["eplan_tag"] == "-BG1"
    assert component["signals"] == [
        {
            "signal_type": "di",
            "meaning": "retracted",
            "confirms_position_id": retracted["id"],
            "drives_position_id": None,
            "safety": True,
            "address": "I150.0",
            "tag_suffix": None,
            "tag_name": None,
            "kind_signal_id": None,
        }
    ]

    # Another device may not reuse the tag.
    second = await _create_device(
        writer,
        ctx,
        components=[{"role_id": ctx["role"]["id"], "eplan_tag": "-BG1"}],
    )
    assert second.status_code == 409
    assert second.json()["code"] == "ProductDeviceEplanTagTakenError"

    # Removing the component on update deletes it.
    body = _device_body(ctx, components=[])
    updated = await writer.put(
        f"{API_WEB}/product-devices/{device_id}",
        json={
            **body,
            "expected_edit_version": await row_version(
                writer, f"{API_WEB}/product-devices/{device_id}"
            ),
        },
    )
    assert updated.status_code == 200, updated.text
    refetched = (await writer.get(f"{API_WEB}/product-devices/{device_id}")).json()
    assert refetched["components"] == []
    assert refetched["number"] == 1


async def test_product_devices_position_of_other_kind_is_refused(
    writer: httpx.AsyncClient,
) -> None:
    ctx = await _setup(writer)
    other_kind = await _kind(writer)
    r = await _create_device(writer, ctx, initial_position_id=other_kind["positions"][0]["id"])
    assert r.status_code == 422
    assert r.json()["code"] == "ProductDeviceReferenceInvalidError"


async def test_product_devices_name_preview(writer: httpx.AsyncClient) -> None:
    ctx = await _setup(writer)
    assert (await _create_device(writer, ctx)).status_code == 201
    url = f"{API_WEB}/products/{ctx['product']['id']}/devices/name-preview"

    preview = await writer.post(url, json=_device_body(ctx))
    assert preview.status_code == 200, preview.text
    assert preview.json()["number"] == 2
    assert preview.json()["full_name_ascii"] == "M26001_B01_W4_L_Hubzylinder_Einfoerderung_P2"
    assert preview.json()["taken"] is False

    taken = await writer.post(url, json=_device_body(ctx, number=1))
    assert taken.json()["taken"] is True

    invalid = await writer.post(url, json=_device_body(ctx, name="A:B"))
    assert invalid.json()["invalid_characters"] == [":"]


async def test_product_devices_edit_needs_product_rights(
    writer: httpx.AsyncClient, auth_client: Any
) -> None:
    ctx = await _setup(writer)
    outsider = await auth_client(
        permissions=[Permission.WRITE_PROJECTS], username="outsider", email="outsider@example.com"
    )
    r = await outsider.post(
        f"{API_WEB}/products/{ctx['product']['id']}/devices", json=_device_body(ctx)
    )
    assert r.status_code == 403


# ── Calculations ──────────────────────────────────────────────────────


def _calculation(**overrides: Any) -> dict[str, Any]:
    return {
        "tool": "fit_calculator",
        "title": "Cylinder force",
        "inputs": {"d": 32},
        "results": {"force": 482},
        "input_version": 1,
        "engine_version": 1,
    } | overrides


async def test_product_devices_calculation_freezes_device_name_on_release(
    writer: httpx.AsyncClient,
) -> None:
    ctx = await _setup(writer)
    device = (await _create_device(writer, ctx)).json()
    product_id = ctx["product"]["id"]

    created = await writer.post(
        f"{API_WEB}/calculations",
        json=_calculation(product_id=product_id, product_device_id=device["id"]),
    )
    assert created.status_code == 201, created.text
    draft = await writer.post(
        f"{API_WEB}/calculations",
        json=_calculation(product_id=product_id, product_device_id=device["id"]),
    )
    assert draft.status_code == 201, draft.text
    calc_id = created.json()["id"]
    assert created.json()["product_device_name"] == device["full_name_utf8"]

    released = await writer.post(f"{API_WEB}/calculations/{calc_id}/release")
    assert released.status_code == 200, released.text

    renamed = await writer.put(
        f"{API_WEB}/product-devices/{device['id']}",
        json={
            **_device_body(ctx, name="Hubzylinder"),
            "expected_edit_version": await row_version(
                writer, f"{API_WEB}/product-devices/{device['id']}"
            ),
        },
    )
    assert renamed.status_code == 200, renamed.text

    frozen = (await writer.get(f"{API_WEB}/calculations/{calc_id}")).json()
    assert frozen["product_device_name"] == "M26001 B01-W4-L Hubzylinder Einförderung P1"
    live = (await writer.get(f"{API_WEB}/calculations/{draft.json()['id']}")).json()
    assert live["product_device_name"] == "M26001 B01-W4-L Hubzylinder P1"


async def test_product_devices_calculation_refuses_device_of_other_product(
    writer: httpx.AsyncClient,
) -> None:
    ctx = await _setup(writer)
    device = (await _create_device(writer, ctx)).json()
    other = await _product(writer, "M26002")

    r = await writer.post(
        f"{API_WEB}/calculations",
        json=_calculation(product_id=other["id"], product_device_id=device["id"]),
    )
    assert r.status_code == 422
    assert r.json()["code"] == "ProductDeviceReferenceInvalidError"


async def test_product_devices_link_and_unlink_a_draft_calculation(
    writer: httpx.AsyncClient,
) -> None:
    ctx = await _setup(writer)
    device = (await _create_device(writer, ctx)).json()
    product_id = ctx["product"]["id"]
    calc = (
        await writer.post(f"{API_WEB}/calculations", json=_calculation(product_id=product_id))
    ).json()

    linked = await writer.put(
        f"{API_WEB}/calculations/{calc['id']}/device", json={"product_device_id": device["id"]}
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()["product_device_id"] == device["id"]
    listed = (
        await writer.get(f"{API_WEB}/calculations", params={"product_device_id": device["id"]})
    ).json()
    assert [c["id"] for c in listed["items"]] == [calc["id"]]

    unlinked = await writer.put(
        f"{API_WEB}/calculations/{calc['id']}/device", json={"product_device_id": None}
    )
    assert unlinked.status_code == 200, unlinked.text
    assert unlinked.json()["product_device_id"] is None
    listed = (
        await writer.get(f"{API_WEB}/calculations", params={"product_device_id": device["id"]})
    ).json()
    assert listed["items"] == []


async def test_product_devices_link_refuses_a_released_calculation_and_a_foreign_device(
    writer: httpx.AsyncClient,
) -> None:
    ctx = await _setup(writer)
    device = (await _create_device(writer, ctx)).json()
    other = await _product(writer, "M26002")
    calc = (
        await writer.post(f"{API_WEB}/calculations", json=_calculation(product_id=other["id"]))
    ).json()

    foreign = await writer.put(
        f"{API_WEB}/calculations/{calc['id']}/device", json={"product_device_id": device["id"]}
    )
    assert foreign.status_code == 422
    assert foreign.json()["code"] == "ProductDeviceReferenceInvalidError"

    assert (await writer.post(f"{API_WEB}/calculations/{calc['id']}/release")).status_code == 200
    released = await writer.put(
        f"{API_WEB}/calculations/{calc['id']}/device", json={"product_device_id": None}
    )
    assert released.status_code == 409
    assert released.json()["code"] == "CalculationReleasedError"


async def test_product_devices_link_refuses_while_someone_else_edits(
    writer: httpx.AsyncClient, auth_client: Any
) -> None:
    ctx = await _setup(writer)
    device = (await _create_device(writer, ctx)).json()
    calc = (
        await writer.post(
            f"{API_WEB}/calculations", json=_calculation(product_id=ctx["product"]["id"])
        )
    ).json()
    manager: httpx.AsyncClient = await auth_client(
        permissions=[Permission.WRITE_CALCULATIONS, Permission.MANAGE_CALCULATIONS],
        username="calc-manager",
        email="calc-manager@example.com",
    )
    assert (
        await manager.post(f"{API_WEB}/calculations/{calc['id']}/lock", json={})
    ).status_code == 200

    r = await writer.put(
        f"{API_WEB}/calculations/{calc['id']}/device", json={"product_device_id": device["id"]}
    )
    assert r.status_code == 409


# ── Renumbering ───────────────────────────────────────────────────────


async def test_product_devices_renumber_impact(writer: httpx.AsyncClient) -> None:
    ctx = await _setup(writer)
    device = (await _create_device(writer, ctx)).json()
    product_id = ctx["product"]["id"]
    calc = await writer.post(
        f"{API_WEB}/calculations",
        json=_calculation(product_id=product_id, product_device_id=device["id"]),
    )
    await writer.post(f"{API_WEB}/calculations/{calc.json()['id']}/release")

    r = await writer.get(
        f"{API_WEB}/products/{product_id}/renumber-impact", params={"new_number": "M26009"}
    )
    assert r.status_code == 200, r.text
    assert r.json() == {
        "device_count": 1,
        "device_examples": [
            {
                "old_name": "M26001_B01_W4_L_Hubzylinder_Einfoerderung_P1",
                "new_name": "M26009_B01_W4_L_Hubzylinder_Einfoerderung_P1",
            }
        ],
        "released_document_count": 1,
        "export_count": 0,
    }


async def test_product_devices_one_component_confirms_both_end_positions(
    writer: httpx.AsyncClient,
) -> None:
    ctx = await _setup(writer)
    retracted, extended, _intermediate = ctx["kind"]["positions"]

    created = await _create_device(
        writer,
        ctx,
        components=[
            {
                "role_id": ctx["role"]["id"],
                "signals": [
                    {
                        "signal_type": "di",
                        "meaning": "retracted",
                        "confirms_position_id": retracted["id"],
                    },
                    {
                        "signal_type": "di",
                        "meaning": "extended",
                        "confirms_position_id": extended["id"],
                    },
                ],
            }
        ],
    )
    assert created.status_code == 201, created.text
    fetched = (await writer.get(f"{API_WEB}/product-devices/{created.json()['id']}")).json()
    confirmed = [s["confirms_position_id"] for s in fetched["components"][0]["signals"]]
    assert confirmed == [retracted["id"], extended["id"]]


async def test_product_devices_output_signal_cannot_confirm_a_position(
    writer: httpx.AsyncClient,
) -> None:
    ctx = await _setup(writer)
    retracted = ctx["kind"]["positions"][0]
    r = await _create_device(
        writer,
        ctx,
        components=[
            {
                "role_id": ctx["role"]["id"],
                "signals": [
                    {
                        "signal_type": "do",
                        "meaning": "extend",
                        "confirms_position_id": retracted["id"],
                    }
                ],
            }
        ],
    )
    assert r.status_code == 422
    assert r.json()["code"] == "ProductDeviceReferenceInvalidError"


@pytest.mark.parametrize(
    "signal",
    [
        {"signal_type": "do", "meaning": "x", "confirms_position_id": "retracted"},
        {"signal_type": "di", "meaning": "x", "drives_position_id": "retracted"},
        {"signal_type": "bus", "meaning": "x", "safety": True},
        {"signal_type": "di", "meaning": "x", "address": "Eingang 1"},
        {"signal_type": "do", "meaning": "x", "tag_suffix": "Aus-fahren"},
    ],
)
async def test_product_devices_refuse_signals_that_do_not_fit(
    writer: httpx.AsyncClient, signal: dict[str, Any]
) -> None:
    ctx = await _setup(writer)
    retracted = ctx["kind"]["positions"][0]["id"]
    for key in ("confirms_position_id", "drives_position_id"):
        if signal.get(key) == "retracted":
            signal = {**signal, key: retracted}
    r = await _create_device(
        writer, ctx, components=[{"role_id": ctx["role"]["id"], "signals": [signal]}]
    )
    assert r.status_code == 422, r.text


async def test_product_devices_output_drives_a_position(writer: httpx.AsyncClient) -> None:
    ctx = await _setup(writer)
    extended = ctx["kind"]["positions"][1]["id"]
    r = await _create_device(
        writer,
        ctx,
        components=[
            {
                "role_id": ctx["role"]["id"],
                "signals": [
                    {
                        "signal_type": "do",
                        "meaning": "extend",
                        "drives_position_id": extended,
                        "tag_suffix": "Ausfahren",
                    }
                ],
            }
        ],
    )
    assert r.status_code == 201, r.text
    signal = r.json()["components"][0]["signals"][0]
    assert (signal["drives_position_id"], signal["tag_suffix"]) == (extended, "Ausfahren")


async def test_product_device_kind_positions_keep_their_plc_names(
    writer: httpx.AsyncClient,
) -> None:
    body = {
        "label": {"enGB": "Cylinder"},
        "positions": [
            {
                "label": {"enGB": "Retracted"},
                "plc_state_name": "EIN",
                "plc_command_name": "Einfahren",
            },
            {"label": {"enGB": "Extended"}, "plc_state_name": " ", "plc_command_name": None},
        ],
    }
    created = await writer.post(f"{RESOURCES}/kinds", json=body)
    assert created.status_code == 201, created.text
    first, second = created.json()["positions"]
    assert (first["plc_state_name"], first["plc_command_name"]) == ("EIN", "Einfahren")
    assert (second["plc_state_name"], second["plc_command_name"]) == (None, None)

    body["positions"][0]["plc_state_name"] = "EIN-1"
    refused = await writer.post(f"{RESOURCES}/kinds", json=body)
    assert refused.status_code == 422


async def test_product_device_signals_pick_a_signal_of_their_kind(
    writer: httpx.AsyncClient,
) -> None:
    ctx = await _setup(writer)
    kind = ctx["kind"]
    updated = await writer.put(
        f"{RESOURCES}/kinds/{kind['id']}",
        json={
            "label": kind["label"],
            "positions": [{"id": p["id"], "label": p["label"]} for p in kind["positions"]],
            "signals": [
                {"label": {"enGB": "Fault"}, "signal_type": "di", "plc_name": "Stoerung"},
                {"label": {"enGB": "Enable"}, "signal_type": "do", "plc_name": "Freigabe"},
            ],
        },
    )
    assert updated.status_code == 200, updated.text
    fault, enable = updated.json()["signals"]
    assert (fault["signal_type"], fault["plc_name"]) == ("di", "Stoerung")
    retracted = kind["positions"][0]["id"]

    # A signal that picks a kind signal or names a position needs no meaning.
    r = await _create_device(
        writer,
        ctx,
        components=[
            {
                "role_id": ctx["role"]["id"],
                "signals": [
                    {"signal_type": "di", "kind_signal_id": fault["id"]},
                    {"signal_type": "di", "confirms_position_id": retracted},
                ],
            }
        ],
    )
    assert r.status_code == 201, r.text
    picked, confirming = r.json()["components"][0]["signals"]
    assert (picked["kind_signal_id"], picked["meaning"]) == (fault["id"], "")
    assert confirming["meaning"] == ""

    for refused in (
        # The kind signal sets the type.
        {"signal_type": "di", "kind_signal_id": enable["id"]},
        # A position or a kind signal, not both.
        {"signal_type": "di", "kind_signal_id": fault["id"], "confirms_position_id": retracted},
        # Neither needs a meaning.
        {"signal_type": "di"},
    ):
        r = await _create_device(
            writer,
            ctx,
            name=f"Refused {len(refused)}",
            components=[{"role_id": ctx["role"]["id"], "signals": [refused]}],
        )
        assert r.status_code == 422, (refused, r.text)

    # A kind signal needs a PLC name.
    missing = await writer.put(
        f"{RESOURCES}/kinds/{kind['id']}",
        json={
            "label": kind["label"],
            "signals": [{"label": {"enGB": "Ready"}, "signal_type": "di", "plc_name": " "}],
        },
    )
    assert missing.status_code == 422


async def test_product_devices_driven_by_another_device(writer: httpx.AsyncClient) -> None:
    ctx = await _setup(writer)
    driver = (await _create_device(writer, ctx, name="Spannzylinder")).json()
    follower = await _create_device(writer, ctx, name="Spannzylinder", driven_by_id=driver["id"])
    assert follower.status_code == 201, follower.text
    follower_id = follower.json()["id"]
    fetched = (await writer.get(f"{API_WEB}/product-devices/{follower_id}")).json()
    assert (fetched["driven_by_id"], fetched["driven_position_map"]) == (driver["id"], {})

    # No chains: a driven device drives nothing, and a driver is not driven.
    chained = await _create_device(writer, ctx, name="Third", driven_by_id=follower_id)
    assert chained.status_code == 422
    back = await writer.put(
        f"{API_WEB}/product-devices/{driver['id']}",
        json={
            **_device_body(ctx, name="Spannzylinder", driven_by_id=follower_id),
            "expected_edit_version": await row_version(
                writer, f"{API_WEB}/product-devices/{driver['id']}"
            ),
        },
    )
    assert back.status_code == 422
    selfish = await writer.put(
        f"{API_WEB}/product-devices/{driver['id']}",
        json={
            **_device_body(ctx, name="Spannzylinder", driven_by_id=driver["id"]),
            "expected_edit_version": await row_version(
                writer, f"{API_WEB}/product-devices/{driver['id']}"
            ),
        },
    )
    assert selfish.status_code == 422


async def test_product_devices_of_a_kind_without_driving_medium(writer: httpx.AsyncClient) -> None:
    ctx = await _setup(writer)
    button = await writer.post(
        f"{RESOURCES}/kinds",
        json={
            "label": {"enGB": "Push button"},
            "without_driving_medium": True,
            "positions": [{"label": {"enGB": "Pressed"}, "plc_state_name": "gedrueckt"}],
        },
    )
    assert button.status_code == 201, button.text
    assert button.json()["without_driving_medium"] is True
    regular = ctx
    ctx = {**ctx, "kind": button.json()}

    first = await _create_device(
        writer, ctx, location="", name="Taster Start", driving_medium_id=None
    )
    assert first.status_code == 201, first.text
    assert first.json()["name_utf8"] == "Taster Start"
    assert first.json()["driving_medium_letter"] is None
    second = await _create_device(
        writer, ctx, location="", name="Taster Start", driving_medium_id=None
    )
    assert second.json()["name_ascii"] == "Taster_Start_2"

    with_medium = await _create_device(writer, ctx, name="Taster Stopp")
    assert with_medium.status_code == 422
    without = await _create_device(writer, regular, name="Zylinder", driving_medium_id=None)
    assert without.status_code == 422


async def test_product_device_completeness(writer: httpx.AsyncClient, auth_client: Any) -> None:
    ctx = await _setup(writer)
    planner = await auth_client(
        permissions=[Permission.WRITE_SEQUENCES], username="planner", email="planner@example.com"
    )
    device = (await _create_device(writer, ctx, name="Spannzylinder")).json()
    follower = (
        await _create_device(writer, ctx, name="Spannzylinder", driven_by_id=device["id"])
    ).json()
    url = f"{API_WEB}/products/{ctx['product']['id']}/device-completeness"

    checks = f"{API_WEB}/product-devices/{device['id']}/checks"
    assert (await writer.put(f"{checks}/eplan", json={"checked": True})).status_code == 204
    assert (await writer.put(f"{checks}/cad_assembly", json={"checked": True})).status_code == 204
    assert (await writer.put(f"{checks}/cad_assembly", json={"checked": False})).status_code == 204
    rows = {r["device_id"]: r for r in (await writer.get(url)).json()}
    assert [c["plan"] for c in rows[device["id"]]["checks"]] == ["eplan"]
    assert rows[device["id"]]["sequence_coverage"] == "none"

    # A draft sequence that moves the driver covers its follower too.
    extended = ctx["kind"]["positions"][1]["id"]
    sequence = await planner.post(
        f"{API_WEB}/sequences",
        json={
            "product_id": ctx["product"]["id"],
            "name": "Automatic",
            "steps": [
                {
                    "key": "s1",
                    "actions": [
                        {
                            "key": "a1",
                            "kind": "device",
                            "device_id": device["id"],
                            "position_id": extended,
                        }
                    ],
                    "transitions": [{"key": "t1", "target": "end"}],
                }
            ],
        },
    )
    assert sequence.status_code == 201, sequence.text
    rows = {r["device_id"]: r for r in (await writer.get(url)).json()}
    assert rows[follower["id"]]["sequence_coverage"] == "draft"

    # Renaming takes the ticks away.
    renamed = await writer.put(
        f"{API_WEB}/product-devices/{device['id']}",
        json={
            **_device_body(ctx, name="Klemmzylinder"),
            "expected_edit_version": await row_version(
                writer, f"{API_WEB}/product-devices/{device['id']}"
            ),
        },
    )
    assert renamed.status_code == 200, renamed.text
    rows = {r["device_id"]: r for r in (await writer.get(url)).json()}
    assert rows[device["id"]]["checks"] == []


# ── Changer ───────────────────────────────────────────────────────────


async def test_product_devices_and_resources_record_the_changing_user(
    writer: httpx.AsyncClient, auth_client: Any
) -> None:
    ctx = await _setup(writer)
    created = await _create_device(writer, ctx)
    assert created.status_code == 201, created.text
    device = created.json()
    editor = await auth_client(
        permissions=PERMISSIONS, username="editor", email="editor@example.com"
    )

    updated = await editor.put(
        f"{API_WEB}/product-devices/{device['id']}",
        json={
            **_device_body(ctx, name="Klemmzylinder"),
            "expected_edit_version": await row_version(
                editor, f"{API_WEB}/product-devices/{device['id']}"
            ),
        },
    )
    option = await editor.put(
        f"{RESOURCES}/options/{ctx['role']['id']}", json={"label": {"enGB": "Proximity sensor"}}
    )
    kind = await editor.put(
        f"{RESOURCES}/kinds/{ctx['kind']['id']}",
        json={"label": {"enGB": "Linear drive"}, "positions": [], "parameters": []},
    )

    for response, before in ((updated, device), (option, ctx["role"]), (kind, ctx["kind"])):
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["creator_id"] == before["creator_id"]
        assert body["changed_by_id"] not in (None, before["creator_id"])
        assert body["changed_by"]["id"] == body["changed_by_id"]
    reread = (await writer.get(f"{API_WEB}/product-devices/{device['id']}")).json()
    assert reread["changed_by_id"] == updated.json()["changed_by_id"]


async def test_a_device_edit_moves_its_version_also_when_only_components_change(
    writer: httpx.AsyncClient,
) -> None:
    ctx = await _setup(writer)
    created = await _create_device(writer, ctx)
    assert created.status_code == 201, created.text
    device = created.json()
    url = f"{API_WEB}/product-devices/{device['id']}"

    unchanged = await writer.put(url, json={**_device_body(ctx), "expected_edit_version": 0})
    with_component = await writer.put(
        url,
        json={
            **_device_body(ctx, components=[{"role_id": ctx["role"]["id"], "eplan_tag": "-BG1"}]),
            "expected_edit_version": 0,
        },
    )
    stale = await writer.put(url, json={**_device_body(ctx), "expected_edit_version": 0})
    without = await writer.put(url, json=_device_body(ctx))

    assert unchanged.json()["edit_version"] == 0
    assert with_component.json()["edit_version"] == 1
    assert (stale.status_code, without.status_code) == (409, 422)
