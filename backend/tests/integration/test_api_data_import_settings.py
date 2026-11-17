"""
The data import settings end to end: the admin tab's read and write
(permissions, validation, the audit entry), the profile any signed-in user
reads before an upload, and the row limit the demand imports enforce on
validate and commit.
"""

from src.bootstrap.adapters.outbound.persistence.admin_settings_seed import _data_import_defaults
from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.catalogue.domain.entities.admin_settings.data_import import DataImportProfile
from src.modules.catalogue.domain.value_objects.data_import_type import DataImportType
from src.modules.platform.domain.value_objects.permission import Permission

BASE = "/api/v1/web/admin/settings/data-import"
PROFILE = "/api/v1/web/data-import/profiles"
AUDIT = "/api/v1/web/admin/settings/audit"


async def _seed(db) -> None:
    """The seeded settings plus a few column names, as an admin imports them,
    so a test can tell stored names from the empty seed."""
    settings = _data_import_defaults()
    settings.profiles[DataImportType.BOUGHT_ITEM_DEMAND.value] = DataImportProfile(
        column_names={"quantity": ["Menge", "Quantity"]}
    )
    settings.profiles[DataImportType.MADE_ITEM_DEMAND.value] = DataImportProfile(
        column_names={"quantity": ["Menge"]}
    )
    await SqlAlchemyAdminSettingsRepository(db).save_data_import(settings)
    await db.commit()


def _profile(body: dict, import_type: str) -> dict:
    return next(p for p in body["profiles"] if p["import_type"] == import_type)


async def test_data_import_settings_lists_every_import_with_all_fields(auth_client, db) -> None:
    await _seed(db)
    client = await auth_client(permissions=[Permission.READ_SETTINGS])

    resp = await client.get(BASE)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [p["import_type"] for p in body["profiles"]] == [
        "bought_item_create",
        "bought_item_demand",
        "made_item_demand",
    ]
    made = _profile(body, "made_item_demand")
    assert [f["key"] for f in made["fields"]] == [
        "project_number",
        "quantity",
        "part_number",
        "revision",
        "article_name",
        "desired_delivery_date",
        "note",
    ]
    assert made["header_row"] is None
    assert made["max_rows"] == 100


async def test_data_import_settings_without_a_row_reads_empty_defaults(auth_client) -> None:
    client = await auth_client(permissions=[Permission.READ_SETTINGS])

    resp = await client.get(BASE)

    assert resp.status_code == 200, resp.text
    for profile in resp.json()["profiles"]:
        assert all(f["column_names"] == [] for f in profile["fields"])


async def test_data_import_settings_need_their_permissions(auth_client) -> None:
    nobody = await auth_client(permissions=[])
    reader = await auth_client(
        permissions=[Permission.READ_SETTINGS], username="reader", email="reader@example.com"
    )

    assert (await nobody.get(BASE)).status_code == 403
    assert (await reader.put(BASE, json={"profiles": []})).status_code == 403


async def test_data_import_settings_put_stores_one_profile_and_audits_it(auth_client, db) -> None:
    await _seed(db)
    client = await auth_client(permissions=Permission.ALL)

    resp = await client.put(
        BASE,
        json={
            "profiles": [
                {
                    "import_type": "bought_item_demand",
                    "header_row": 3,
                    "data_offset": 2,
                    "max_rows": 250,
                    "column_names": {"quantity": [" Stk ", "stk"], "project_number": ["Job"]},
                }
            ]
        },
    )

    assert resp.status_code == 200, resp.text
    demand = _profile(resp.json(), "bought_item_demand")
    assert (demand["header_row"], demand["data_offset"], demand["max_rows"]) == (3, 2, 250)
    fields = {f["key"]: f["column_names"] for f in demand["fields"]}
    assert fields["quantity"] == ["Stk"]
    assert fields["project_number"] == ["Job"]
    assert fields["unit"] == []
    # An unlisted import keeps its stored column names.
    made = _profile((await client.get(BASE)).json(), "made_item_demand")
    assert any(f["column_names"] for f in made["fields"])
    audit = (await client.get(AUDIT, params={"settings_domain": "data_import"})).json()
    assert audit["total"] == 1
    assert "bought_item_demand" in audit["items"][0]["summary"]


async def test_data_import_settings_put_refuses_a_name_on_two_fields(auth_client) -> None:
    client = await auth_client(permissions=Permission.ALL)

    resp = await client.put(
        BASE,
        json={
            "profiles": [
                {
                    "import_type": "made_item_demand",
                    "column_names": {"note": ["Info"], "article_name": ["info"]},
                }
            ]
        },
    )

    assert resp.status_code == 400
    assert resp.json()["code"] == "DataImportSettingsInvalidError"


async def test_data_import_settings_put_refuses_a_limit_above_the_cap(auth_client) -> None:
    client = await auth_client(permissions=Permission.ALL)

    resp = await client.put(
        BASE, json={"profiles": [{"import_type": "made_item_demand", "max_rows": 5000}]}
    )

    assert resp.status_code == 422


async def test_data_import_profile_is_readable_by_any_signed_in_user(auth_client, db) -> None:
    await _seed(db)
    client = await auth_client(permissions=[])

    resp = await client.get(f"{PROFILE}/bought_item_demand")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["import_type"] == "bought_item_demand"
    quantity = next(f for f in body["fields"] if f["key"] == "quantity")
    assert "Menge" in quantity["column_names"]


async def test_data_import_profile_refuses_an_unknown_import_type(auth_client) -> None:
    client = await auth_client(permissions=[])

    assert (await client.get(f"{PROFILE}/nonsense")).status_code == 422


async def test_data_import_demand_validate_refuses_more_rows_than_the_limit(
    auth_client, db
) -> None:
    await _seed(db)
    admin = await auth_client(permissions=Permission.ALL)
    put = await admin.put(
        BASE, json={"profiles": [{"import_type": "bought_item_demand", "max_rows": 1}]}
    )
    assert put.status_code == 200, put.text
    row = {
        "row_index": 0,
        "project_number": "P-1",
        "quantity": 1,
        "unit": "pcs",
        "part_number": "X-1",
    }

    resp = await admin.post(
        "/api/v1/web/bought-items-demands/batch/validate",
        json={"rows": [row, {**row, "row_index": 1}]},
    )

    assert resp.status_code == 400, resp.text
    assert resp.json()["code"] == "DataImportRowLimitExceededError"
