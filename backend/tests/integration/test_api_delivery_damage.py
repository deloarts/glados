"""
Damaged goods at deliveries, through HTTP and read back with a separate
request. A booking records whether damage was noted on the carrier's
delivery note, a single delivery and deliver-all alike. A correction with a
rejection takes accepted pieces back as rejected ones after receipt: lost
pieces leave the line delivered with its rejected totals grown, pieces sent
back reopen it, and a correction with neither a reason nor a rejection
answers 422. A receiver uploads pictures of a delivery row, listed with the
order's files and naming the row, and deletes them again, while a file of
the order itself still needs write:orders; a row of another line answers
404 and a caller without receive:deliveries 403.
"""

from datetime import UTC
from datetime import datetime
from typing import Any

import pytest
from sqlalchemy import text

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.platform.const import API_WEB
from src.modules.platform.domain.entities.admin_settings.storage import AdminStorageSettings
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project
from tests.integration._suppliers import seed_supplier

ORDERS = f"{API_WEB}/orders"
DELIVER = f"{API_WEB}/bought-items-allocations/order-item"
_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture(autouse=True)
async def _supplier(db) -> None:
    await seed_supplier(db)


@pytest.fixture
async def storage(db, tmp_path, monkeypatch):
    """Enables the local storage provider, rooted in a temp dir."""
    from src.modules.platform.infrastructure.config.settings import cfg

    media = tmp_path / "media"
    media.mkdir()
    monkeypatch.setattr(cfg.local_storage, "base_dir", str(media))
    await db.execute(text("DELETE FROM admin_storage_settings"))
    await db.commit()
    await SqlAlchemyAdminSettingsRepository(db).save_storage(
        AdminStorageSettings(
            id=1,
            provider="local",
            enabled=True,
            endpoint_url=None,
            public_endpoint_url=None,
            bucket_name=None,
            access_key=None,
            secret_key=None,
            region=None,
            use_ssl=False,
            backup_enabled=False,
            backup_path="backups",
            backup_cron=None,
            backup_retention_count=3,
        )
    )
    await db.commit()
    return media


@pytest.fixture
async def manager(db, auth_client) -> Any:
    await db.commit()
    return await auth_client(
        permissions=[
            Permission.WRITE_ORDERS,
            Permission.MANAGE_ORDERS,
            Permission.RECEIVE_DELIVERIES,
        ]
    )


@pytest.fixture
async def receiver(auth_client) -> Any:
    return await auth_client(
        permissions=[Permission.RECEIVE_DELIVERIES],
        username="receiver",
        email="receiver@example.com",
    )


@pytest.fixture
async def project_id(db, manager) -> int:
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=1, project_number="P-400")
    )
    await db.commit()
    return project.id


async def _order(client: Any) -> int:
    created = await client.post(f"{ORDERS}/", json={"supplier_id": 1})
    assert created.status_code == 201, created.text
    return int(created.json()["id"])


async def _ordered_line(client: Any, order_id: int, project_id: int) -> int:
    """A line of 10 on the order, marked ordered."""
    added = await client.post(
        f"{ORDERS}/{order_id}/items",
        json={
            "order_id": order_id,
            "supplier_id": 1,
            "project_id": project_id,
            "virtual_name": "Bracket",
            "quantity": 10,
            "unit": "pcs",
        },
    )
    assert added.status_code == 201, added.text
    line_id = int(added.json()["id"])
    marked = await client.put(f"{ORDERS}/{order_id}/items/{line_id}/mark-ordered")
    assert marked.status_code == 200, marked.text
    return line_id


async def _line(client: Any, order_id: int, line_id: int) -> dict[str, Any]:
    response = await client.get(f"{ORDERS}/{order_id}")
    assert response.status_code == 200, response.text
    return next(item for item in response.json()["items"] if item["id"] == line_id)


async def _delivered_line(client: Any, project_id: int) -> tuple[int, int, dict[str, Any]]:
    """An order with one line of 10, all of it delivered, and the line."""
    order_id = await _order(client)
    line_id = await _ordered_line(client, order_id, project_id)
    booked = await client.put(f"{DELIVER}/{line_id}/deliver", params={"quantity": 10})
    assert booked.status_code == 200, booked.text
    return order_id, line_id, await _line(client, order_id, line_id)


async def test_a_delivery_records_the_damage_noted_on_the_delivery_note(
    manager, project_id: int
) -> None:
    order_id = await _order(manager)
    line_id = await _ordered_line(manager, order_id, project_id)

    booked = await manager.put(
        f"{DELIVER}/{line_id}/deliver",
        params={"quantity": 4},
        json={"delivery_note_number": "LS-1", "damage_noted_on_delivery_note": True},
    )
    plain = await manager.put(f"{DELIVER}/{line_id}/deliver", params={"quantity": 2})

    assert (booked.status_code, plain.status_code) == (200, 200), booked.text
    line = await _line(manager, order_id, line_id)
    rows = sorted(line["delivery_records"], key=lambda r: r["id"])
    assert [r["damage_noted_on_delivery_note"] for r in rows] == [True, False]


async def test_deliver_all_records_the_damage_noted_on_every_row(manager, project_id: int) -> None:
    order_id = await _order(manager)
    first = await _ordered_line(manager, order_id, project_id)
    second = await _ordered_line(manager, order_id, project_id)

    response = await manager.put(
        f"{ORDERS}/{order_id}/deliver-all-items",
        json={"delivery_note_number": "LS-2", "damage_noted_on_delivery_note": True},
    )

    assert response.status_code == 200, response.text
    for line_id in (first, second):
        (row,) = (await _line(manager, order_id, line_id))["delivery_records"]
        assert (row["delivery_note_number"], row["damage_noted_on_delivery_note"]) == (
            "LS-2",
            True,
        )


async def test_lost_pieces_after_receipt_leave_the_line_delivered(manager, project_id: int) -> None:
    order_id, line_id, line = await _delivered_line(manager, project_id)
    (row,) = line["delivery_records"]

    response = await manager.post(
        f"{ORDERS}/{order_id}/items/{line_id}/deliveries/{row['id']}/correct",
        json={
            "quantity": 3,
            "rejection": {
                "rejection_reason": "transport_damage",
                "rejection_outcome": "lost",
                "rejection_note": " Crushed corner ",
            },
            "expected_edit_version": line["edit_version"],
        },
    )

    assert response.status_code == 200, response.text
    line = await _line(manager, order_id, line_id)
    assert line["status"] == "delivered"
    assert (
        line["quantity_delivered"],
        line["quantity_rejected"],
        line["quantity_rejected_lost"],
    ) == (7, 3, 3)
    rejection = max(line["delivery_records"], key=lambda r: r["id"])
    assert (
        rejection["quantity"],
        rejection["quantity_rejected"],
        rejection["rejection_reason"],
        rejection["rejection_outcome"],
        rejection["rejection_note"],
        rejection["corrects_delivery_id"],
        rejection["correction_reason"],
    ) == (-3, 3, "transport_damage", "lost", "Crushed corner", row["id"], None)


async def test_pieces_sent_back_after_receipt_reopen_the_line(manager, project_id: int) -> None:
    order_id, line_id, line = await _delivered_line(manager, project_id)
    (row,) = line["delivery_records"]

    response = await manager.post(
        f"{ORDERS}/{order_id}/items/{line_id}/deliveries/{row['id']}/correct",
        json={
            "quantity": 2,
            "rejection": {"rejection_reason": "supplier_damage", "rejection_outcome": "redeliver"},
            "expected_edit_version": line["edit_version"],
        },
    )

    assert response.status_code == 200, response.text
    line = await _line(manager, order_id, line_id)
    assert (line["status"], line["quantity_delivered"], line["quantity_rejected"]) == (
        "partially_delivered",
        8,
        2,
    )


async def test_a_correction_with_neither_a_reason_nor_a_rejection_is_refused(
    manager, project_id: int
) -> None:
    order_id, line_id, line = await _delivered_line(manager, project_id)
    (row,) = line["delivery_records"]
    url = f"{ORDERS}/{order_id}/items/{line_id}/deliveries/{row['id']}/correct"

    unexplained = await manager.post(
        url, json={"quantity": 1, "expected_edit_version": line["edit_version"]}
    )
    unknown_reason = await manager.post(
        url,
        json={
            "quantity": 1,
            "rejection": {"rejection_reason": "bad_weather", "rejection_outcome": "lost"},
            "expected_edit_version": line["edit_version"],
        },
    )

    assert (unexplained.status_code, unknown_reason.status_code) == (422, 422)
    assert (await _line(manager, order_id, line_id))["quantity_delivered"] == 10


async def test_a_receiver_uploads_and_deletes_a_picture_of_a_delivery_row(
    manager, receiver, storage, project_id: int
) -> None:
    order_id, line_id, line = await _delivered_line(manager, project_id)
    (row,) = line["delivery_records"]

    uploaded = await receiver.post(
        f"{ORDERS}/{order_id}/items/{line_id}/deliveries/{row['id']}/pictures",
        files={"file": ("damage.png", _PNG, "image/png")},
    )

    assert uploaded.status_code == 201, uploaded.text
    picture = uploaded.json()
    assert (picture["category"], picture["delivery_id"], picture["order_id"]) == (
        "picture",
        row["id"],
        order_id,
    )
    listed = await receiver.get(f"{ORDERS}/{order_id}/files")
    assert [(f["id"], f["delivery_id"]) for f in listed.json()] == [(picture["id"], row["id"])]

    deleted = await receiver.delete(f"{ORDERS}/{order_id}/files/{picture['id']}")

    assert deleted.status_code == 204, deleted.text
    assert (await receiver.get(f"{ORDERS}/{order_id}/files")).json() == []


async def test_a_file_of_the_order_itself_still_needs_write_orders(
    manager, receiver, storage, project_id: int
) -> None:
    order_id, _, _ = await _delivered_line(manager, project_id)
    uploaded = await manager.post(
        f"{ORDERS}/{order_id}/files",
        data={"category": "picture"},
        files={"file": ("order.png", _PNG, "image/png")},
    )
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["delivery_id"] is None

    refused = await receiver.delete(f"{ORDERS}/{order_id}/files/{uploaded.json()['id']}")

    assert refused.status_code == 403, refused.text


async def test_a_picture_upload_is_refused_with_its_status_codes(
    manager, auth_client, storage, project_id: int
) -> None:
    order_id, line_id, line = await _delivered_line(manager, project_id)
    (row,) = line["delivery_records"]
    other_order, other_line, other = await _delivered_line(manager, project_id)
    (other_row,) = other["delivery_records"]
    buyer = await auth_client(
        permissions=[Permission.WRITE_ORDERS], username="buyer", email="buyer@example.com"
    )
    picture = {"file": ("damage.png", _PNG, "image/png")}

    forbidden = await buyer.post(
        f"{ORDERS}/{order_id}/items/{line_id}/deliveries/{row['id']}/pictures", files=picture
    )
    other_row_missing = await manager.post(
        f"{ORDERS}/{order_id}/items/{line_id}/deliveries/{other_row['id']}/pictures",
        files=picture,
    )
    other_line_missing = await manager.post(
        f"{ORDERS}/{order_id}/items/{other_line}/deliveries/{other_row['id']}/pictures",
        files=picture,
    )
    not_an_image = await manager.post(
        f"{ORDERS}/{order_id}/items/{line_id}/deliveries/{row['id']}/pictures",
        files={"file": ("note.pdf", b"%PDF-1.4", "application/pdf")},
    )

    assert (
        forbidden.status_code,
        other_row_missing.status_code,
        other_line_missing.status_code,
        not_an_image.status_code,
    ) == (403, 404, 404, 415), not_an_image.text
    for order in (order_id, other_order):
        assert (await manager.get(f"{ORDERS}/{order}/files")).json() == []
