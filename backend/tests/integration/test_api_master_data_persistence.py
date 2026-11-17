"""
Proves that the master data write routes persist what they report. Each
case creates a record, edits it, archives it and restores it over the API,
and after every step reads the record back through a separate request, so
a use case that forgets to commit its unit of work fails here instead of
silently losing the write.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest
from sqlalchemy import select

from src.modules.fulfillment.adapters.outbound.persistence.models.admin_settings_model.production import (
    AdminProductionSettingsOrmModel,
)
from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission


@dataclass(frozen=True)
class _Case:
    path: str
    permissions: list[str]
    create: dict[str, Any]
    update: dict[str, Any]
    checked_field: str
    update_method: str = "put"
    # Creates whatever the record must point at and returns the fields that
    # reference it, merged into both the create and the update body.
    prepare: Callable[[Any], Awaitable[dict[str, Any]]] | None = None


async def _source_item_type(client: Any) -> dict[str, Any]:
    response = await client.post(
        f"{API_WEB}/source-item-types/", json={"name": {"enGB": "Round bar"}}
    )
    assert response.status_code == 201, response.text
    return {"type_id": response.json()["id"]}


@pytest.fixture(autouse=True)
async def _seed_production_settings(db) -> None:
    """Archiving an inspection method reads the production settings, which
    the shared conftest does not seed."""
    if not await db.scalar(select(AdminProductionSettingsOrmModel).filter_by(id=1).limit(1)):
        db.add(
            AdminProductionSettingsOrmModel(
                id=1,
                production_order_number_format="PO-{seq:04d}",
                default_weekly_hours={str(d): 480 for d in range(5)},
                default_external_lead_days=0,
                response_time_days=0,
                require_qa=False,
                default_inspection_method_id=None,
            )
        )
        await db.commit()


CASES = {
    "article-groups": _Case(
        path="article-groups",
        permissions=[Permission.WRITE_ARTICLE_GROUPS],
        create={"name": {"enGB": "Fasteners"}},
        update={"name": {"enGB": "Fasteners, metric"}},
        checked_field="name",
    ),
    "fabrication-methods": _Case(
        path="fabrication-methods",
        permissions=[Permission.WRITE_FABRICATION_METHODS],
        create={"name": {"enGB": "Milling"}},
        update={"name": {"enGB": "Milling, 5 axis"}},
        checked_field="name",
    ),
    "inspection-methods": _Case(
        path="inspection-methods",
        permissions=[Permission.WRITE_INSPECTION_METHODS],
        create={"name": {"enGB": "Visual check"}},
        update={"name": {"enGB": "Visual check, final"}},
        checked_field="name",
    ),
    "production-machine-pools": _Case(
        path="production-machine-pools",
        permissions=[Permission.WRITE_MACHINES],
        create={"name": "Lathes"},
        update={"name": "Lathes, hall 2"},
        checked_field="name",
        update_method="patch",
    ),
    "printers": _Case(
        path="printers",
        permissions=[Permission.WRITE_PRINTERS],
        create={
            "name": "Shipping label printer",
            "kind": "zpl_label",
            "host": "printer.example.local",
            "port": 9100,
            "transport": "raw",
        },
        update={"name": "Shipping label printer, dock 2"},
        checked_field="name",
        update_method="patch",
    ),
    "products": _Case(
        path="products",
        permissions=[Permission.WRITE_PROJECTS, Permission.MANAGE_PROJECTS],
        create={"product_number": "P-100"},
        update={"product_number": "P-101"},
        checked_field="product_number",
    ),
    "production-machines": _Case(
        path="production-machines",
        permissions=[Permission.WRITE_MACHINES],
        create={"internal_name": "MILL-1", "vendor": "Contoso", "model": "VF-2"},
        update={"internal_name": "MILL-1B"},
        checked_field="internal_name",
        update_method="patch",
    ),
    "source-items": _Case(
        path="source-items",
        permissions=[
            Permission.WRITE_SOURCE_ITEMS,
            Permission.DELETE_SOURCE_ITEMS,
            Permission.WRITE_SOURCE_ITEM_TYPES,
        ],
        create={"material": "1.0037"},
        update={"material": "1.4301", "status": "active"},
        checked_field="material",
        prepare=_source_item_type,
    ),
    "source-item-types": _Case(
        path="source-item-types",
        permissions=[Permission.WRITE_SOURCE_ITEM_TYPES],
        create={"name": {"enGB": "Flat bar"}},
        update={"name": {"enGB": "Flat bar, cold drawn"}},
        checked_field="name",
    ),
    "suppliers": _Case(
        path="suppliers",
        permissions=[Permission.WRITE_SUPPLIERS, Permission.DELETE_SUPPLIERS],
        create={"name": "Acme Steel"},
        update={"name": "Acme Steel Ltd"},
        checked_field="name",
    ),
}


@pytest.mark.parametrize("case", list(CASES.values()), ids=list(CASES))
async def test_writes_are_persisted(case: _Case, auth_client) -> None:
    client = await auth_client(permissions=case.permissions)
    base = f"{API_WEB}/{case.path}"
    refs = await case.prepare(client) if case.prepare else {}

    created = await client.post(f"{base}/", json=case.create | refs)
    assert created.status_code == 201, created.text
    record_id = created.json()["id"]

    async def reread() -> dict[str, Any]:
        response = await client.get(f"{base}/{record_id}")
        assert response.status_code == 200, response.text
        return dict(response.json())

    assert (await reread())[case.checked_field] == case.create[case.checked_field]

    # The rows that carry an edit version send the one they read.
    read = await reread()
    version = {"expected_edit_version": read["edit_version"]} if "edit_version" in read else {}
    updated = await getattr(client, case.update_method)(
        f"{base}/{record_id}", json=case.update | refs | version
    )
    assert updated.status_code == 200, updated.text
    assert (await reread())[case.checked_field] == case.update[case.checked_field]

    archived = await client.post(f"{base}/{record_id}/archive")
    assert archived.status_code == 200, archived.text
    assert (await reread())["archived"] is True

    restored = await client.post(f"{base}/{record_id}/restore")
    assert restored.status_code == 200, restored.text
    assert (await reread())["archived"] is False
