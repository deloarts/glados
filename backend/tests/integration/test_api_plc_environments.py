"""
tests/integration/test_api_plc_environments.py

PLC environments over HTTP: the TIA template, creating and editing one with
its prefixes, conversions and export columns, the single default, archiving
and the names unique among live environments, and a product choosing its
environment. Every write is read back through a separate request, so a
missing commit fails here.
"""

from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.adapters.outbound.persistence.models.plc_environment_model import (
    PlcEnvironmentOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.plc_manual_tag_model import (
    PlcManualTagOrmModel,
)
from tests.integration._edit_versions import row_version

URL = f"{API_WEB}/product-device-resources/plc-environments"


PERMISSIONS = [
    Permission.WRITE_PRODUCT_DEVICE_RESOURCES,
    Permission.WRITE_PROJECTS,
    Permission.MANAGE_PROJECTS,
]


@pytest.fixture
async def client(auth_client: Any) -> httpx.AsyncClient:
    c: httpx.AsyncClient = await auth_client(permissions=PERMISSIONS)
    return c


async def _ok(response: httpx.Response, status: int = 200) -> Any:
    assert response.status_code == status, response.text
    return response.json()


async def _create(client: httpx.AsyncClient, name: str, **overrides: Any) -> Any:
    body = await _ok(await client.get(f"{URL}/template"))
    body.update(name=name, **overrides)
    return await _ok(await client.post(URL, json=body), 201)


async def test_plc_environment_template_is_tia(client: httpx.AsyncClient) -> None:
    template = await _ok(await client.get(f"{URL}/template"))
    assert template["prefixes"]["di"] == "di_"
    assert template["prefixes"]["do"] == "dq_"
    assert template["max_tag_length"] == 128
    assert {"source": "-", "target": "_"} in template["conversions"]
    assert template["export_columns"][0] == {"header": "Name", "source": "tag_name", "value": None}


async def test_plc_environment_create_edit_and_single_default(client: httpx.AsyncClient) -> None:
    first = await _create(client, "TIA V19")
    assert first["is_default"] is True  # the first one becomes the default
    second = await _create(client, "TwinCAT", max_tag_length=255, is_default=True)

    listed = await _ok(await client.get(URL))
    defaults = {e["name"]: e["is_default"] for e in listed}
    assert defaults == {"TIA V19": False, "TwinCAT": True}

    body = {k: second[k] for k in (await _ok(await client.get(f"{URL}/template")))}
    body.update(
        prefixes={"di": "I_"}, conversions=[{"source": "ä", "target": "ae"}], is_default=True
    )
    saved = await _ok(await client.put(f"{URL}/{second['id']}", json=body))
    assert saved["prefixes"]["di"] == "I_"
    assert saved["prefixes"]["do"] == ""  # missing keys come back empty
    assert saved["conversions"] == [{"source": "ä", "target": "ae"}]


async def test_plc_environment_rules(client: httpx.AsyncClient) -> None:
    env = await _create(client, "TIA")
    assert (await client.post(URL, json={**env, "name": "tia"})).status_code == 409
    bad = await client.post(URL, json={**env, "name": "X", "max_tag_length": 3})
    assert bad.status_code == 422
    twice = [{"source": "-", "target": "_"}, {"source": "-", "target": ""}]
    assert (
        await client.post(URL, json={**env, "name": "Y", "conversions": twice})
    ).status_code == 422
    assert (
        await client.post(URL, json={**env, "name": "Z", "prefixes": {"xx": "a"}})
    ).status_code == 422
    # The default cannot be archived or taken off.
    assert (await client.post(f"{URL}/{env['id']}/archive")).status_code == 409
    assert (
        await client.put(f"{URL}/{env['id']}", json={**env, "is_default": False})
    ).status_code == 409


async def test_plc_environment_archive_and_product_choice(client: httpx.AsyncClient) -> None:
    await _create(client, "TIA")
    other = await _create(client, "TwinCAT")
    product = await _ok(
        await client.post(
            f"{API_WEB}/products/",
            json={"product_number": "M26001", "plc_environment_id": other["id"]},
        ),
        201,
    )
    assert product["plc_environment_id"] == other["id"]

    await _ok(await client.post(f"{URL}/{other['id']}/archive"))
    assert [e["name"] for e in await _ok(await client.get(URL))] == ["TIA"]
    # A product keeps an environment archived since; a new choice must be live.
    body = {"product_number": "M26001", "plc_environment_id": other["id"]}
    await _ok(
        await client.put(
            f"{API_WEB}/products/{product['id']}",
            json={
                **body,
                "expected_edit_version": await row_version(
                    client, f"{API_WEB}/products/{product['id']}"
                ),
            },
        )
    )
    refused = await client.post(
        f"{API_WEB}/products/", json={"product_number": "M26002", "plc_environment_id": other["id"]}
    )
    assert refused.status_code == 422


async def test_plc_environment_edit_needs_permission(
    client: httpx.AsyncClient, auth_client: Any
) -> None:
    env = await _create(client, "TIA")
    reader = await auth_client(permissions=[], username="reader", email="reader@example.com")
    assert (await reader.get(URL)).status_code == 200
    assert (await reader.put(f"{URL}/{env['id']}", json=env)).status_code == 403


async def test_name_preview_tells_the_longest_tag(client: httpx.AsyncClient) -> None:
    await _create(client, "TIA", max_tag_length=30)
    resources = f"{API_WEB}/product-device-resources"
    medium = await _ok(
        await client.post(
            f"{resources}/options",
            json={"category": "driving_medium", "label": {"enGB": "Pneumatics"}, "letter": "P"},
        ),
        201,
    )
    kind = await _ok(
        await client.post(
            f"{resources}/kinds",
            json={
                "label": {"enGB": "Cylinder"},
                "positions": [{"label": {"enGB": "Retracted"}, "plc_command_name": "Einfahren"}],
            },
        ),
        201,
    )
    product = await _ok(
        await client.post(f"{API_WEB}/products/", json={"product_number": "M26001"}), 201
    )
    preview = await _ok(
        await client.post(
            f"{API_WEB}/products/{product['id']}/devices/name-preview",
            json={
                "location": "B01-B",
                "name": "Spannzylinder",
                "driving_medium_id": medium["id"],
                "kind_id": kind["id"],
            },
        )
    )
    # "fdi_" + "B01_B_Spannzylinder_P1" + "_Einfahren"
    assert (preview["longest_tag_length"], preview["max_tag_length"]) == (36, 30)


async def test_product_plc_tags(client: httpx.AsyncClient) -> None:
    product = await _ok(
        await client.post(f"{API_WEB}/products/", json={"product_number": "M26001"}), 201
    )
    url = f"{API_WEB}/products/{product['id']}/plc-tags"
    assert await _ok(await client.get(url)) == {"environment": None, "tags": []}

    await _create(client, "TIA")
    resources = f"{API_WEB}/product-device-resources"
    medium = await _ok(
        await client.post(
            f"{resources}/options",
            json={"category": "driving_medium", "label": {"enGB": "Pneumatics"}, "letter": "P"},
        ),
        201,
    )
    role = await _ok(
        await client.post(
            f"{resources}/options",
            json={"category": "component_role", "label": {"enGB": "Sensor"}},
        ),
        201,
    )
    kind = await _ok(
        await client.post(
            f"{resources}/kinds",
            json={
                "label": {"enGB": "Cylinder"},
                "positions": [{"label": {"enGB": "Extended"}, "plc_state_name": "AUS"}],
            },
        ),
        201,
    )
    extended = kind["positions"][0]["id"]
    await _ok(
        await client.post(
            f"{API_WEB}/products/{product['id']}/devices",
            json={
                "location": "B01-B",
                "name": "Spannzylinder",
                "driving_medium_id": medium["id"],
                "kind_id": kind["id"],
                "components": [
                    {
                        "role_id": role["id"],
                        "signals": [
                            {
                                "signal_type": "di",
                                "meaning": "extended",
                                "confirms_position_id": extended,
                                "address": "I150.0",
                            }
                        ],
                    }
                ],
            },
        ),
        201,
    )
    listed = await _ok(await client.get(url))
    assert listed["environment"]["name"] == "TIA"
    (tag,) = listed["tags"]
    assert tag["name"] == "di_B01_B_Spannzylinder_P1_AUS"
    assert (tag["address"], tag["tag_table"], tag["too_long"]) == (
        "I150.0",
        "Standard-Variablentabelle",
        False,
    )

    # Renaming the tag in the list gives the signal a name of its own.
    device_url = f"{API_WEB}/product-devices/{tag['device_id']}/signal-tag-name"
    rename = {"component_id": tag["component_id"], "signal_index": 0, "tag_name": "diSpannAus"}
    assert (await client.put(device_url, json=rename)).status_code == 204
    (renamed,) = (await _ok(await client.get(url)))["tags"]
    assert (renamed["name"], renamed["overridden"]) == ("diSpannAus", True)
    bad = {**rename, "tag_name": "di Spann"}
    assert (await client.put(device_url, json=bad)).status_code == 422
    assert (await client.put(device_url, json={**rename, "tag_name": None})).status_code == 204
    (reset,) = (await _ok(await client.get(url)))["tags"]
    assert reset["name"] == "di_B01_B_Spannzylinder_P1_AUS"

    # A manual tag joins the list; one with a taken name is marked twice.
    manual_url = f"{API_WEB}/products/{product['id']}/plc-tags/manual"
    created = await _ok(
        await client.post(
            manual_url,
            json={"name": "di_B01_B_Spannzylinder_P1_AUS", "signal_type": "di", "comment": "Copy"},
        ),
        201,
    )
    tags = (await _ok(await client.get(url)))["tags"]
    assert [t["manual_id"] for t in tags] == [None, created["id"]]
    assert all(t["duplicate"] for t in tags)
    edit = {"name": "dq_Hupe", "signal_type": "do", "address": "Q70.0", "comment": "Horn"}
    tag_url = f"{API_WEB}/plc-manual-tags/{created['id']}"
    assert (await client.put(tag_url, json=edit)).status_code == 204
    manual = (await _ok(await client.get(url)))["tags"][1]
    assert (manual["name"], manual["address"], manual["duplicate"]) == ("dq_Hupe", "Q70.0", False)
    assert (await client.delete(tag_url)).status_code == 204
    assert len((await _ok(await client.get(url)))["tags"]) == 1


async def test_product_discipline_flags_round_trip(client: httpx.AsyncClient) -> None:
    created = await _ok(
        await client.post(
            f"{API_WEB}/products/",
            json={"product_number": "M26001", "contains_pneumatics": True},
        ),
        201,
    )
    assert (created["contains_pneumatics"], created["contains_hydraulics"]) == (True, False)
    body = {"product_number": "M26001", "contains_hydraulics": True, "contains_electrics": True}
    await _ok(
        await client.put(
            f"{API_WEB}/products/{created['id']}",
            json={
                **body,
                "expected_edit_version": await row_version(
                    client, f"{API_WEB}/products/{created['id']}"
                ),
            },
        )
    )
    page = await _ok(await client.get(f"{API_WEB}/products/"))
    (product,) = page["items"]
    flags = [
        product[f"contains_{d}"] for d in ("pneumatics", "hydraulics", "electrics", "robotics")
    ]
    assert flags == [False, True, True, False]


async def test_manual_plc_tags_need_product_rights(
    client: httpx.AsyncClient, auth_client: Any
) -> None:
    product = await _ok(
        await client.post(f"{API_WEB}/products/", json={"product_number": "M26001"}), 201
    )
    outsider = await auth_client(
        permissions=[Permission.WRITE_PROJECTS], username="outsider", email="outsider@example.com"
    )
    r = await outsider.post(
        f"{API_WEB}/products/{product['id']}/plc-tags/manual",
        json={"name": "di_x", "signal_type": "di"},
    )
    assert r.status_code == 403


async def test_plc_environment_and_manual_tag_record_the_changing_user(
    client: httpx.AsyncClient, auth_client: Any, db: AsyncSession
) -> None:
    env = await _create(client, "TIA")
    product = await _ok(
        await client.post(f"{API_WEB}/products/", json={"product_number": "M26001"}), 201
    )
    tag = await _ok(
        await client.post(
            f"{API_WEB}/products/{product['id']}/plc-tags/manual",
            json={"name": "di_x", "signal_type": "di"},
        ),
        201,
    )
    editor = await auth_client(
        permissions=PERMISSIONS, username="editor", email="editor@example.com"
    )

    await _ok(await editor.put(f"{URL}/{env['id']}", json={**env, "max_tag_length": 64}))
    edit = {"name": "dq_Hupe", "signal_type": "do"}
    assert (
        await editor.put(f"{API_WEB}/plc-manual-tags/{tag['id']}", json=edit)
    ).status_code == 204

    env_row = await db.get(PlcEnvironmentOrmModel, env["id"])
    tag_row = await db.get(PlcManualTagOrmModel, tag["id"])
    assert env_row is not None and tag_row is not None
    for row in (env_row, tag_row):
        assert row.changed_by_id is not None
        assert row.changed_by_id != row.creator_id
    assert env_row.changed_by_id == tag_row.changed_by_id
