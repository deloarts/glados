"""
Proves that the print template write routes persist what they report: an
edit and a reset are read back over the API through a fresh request.
Template rows are created as slots at startup in production, so the test
inserts the one row it edits directly.
"""

from datetime import UTC
from datetime import datetime

from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.quality.adapters.outbound.persistence.models.print_template_model import (
    PrintTemplateOrmModel,
)

BASE = f"{API_WEB}/print-templates"


async def _seed_template(db) -> None:
    db.add(PrintTemplateOrmModel(created=datetime(2026, 1, 1, tzinfo=UTC), classifier="lot_label"))
    await db.commit()


async def test_update_and_reset_are_persisted(db, auth_client) -> None:
    await _seed_template(db)
    client = await auth_client(permissions=[Permission.WRITE_PRINTERS])

    resp = await client.patch(f"{BASE}/lot_label", json={"note": "Front door label"})
    assert resp.status_code == 200, resp.text
    assert (await client.get(f"{BASE}/lot_label")).json()["note"] == "Front door label"

    resp = await client.patch(f"{BASE}/lot_label", json={"enabled": True})
    assert resp.status_code == 200, resp.text
    assert (await client.get(f"{BASE}/lot_label")).json()["enabled"] is True
    resp = await client.post(f"{BASE}/lot_label/reset")
    assert resp.status_code == 200, resp.text
    assert (await client.get(f"{BASE}/lot_label")).json()["enabled"] is False


async def test_an_update_naming_the_trigger_and_copies_rule_is_persisted(db, auth_client) -> None:
    """The editor sends trigger and copies rule as plain strings, so the use
    case turns them into their enums before the repository stores them."""
    await _seed_template(db)
    client = await auth_client(permissions=[Permission.WRITE_PRINTERS])

    resp = await client.patch(
        f"{BASE}/lot_label",
        json={"trigger": "lot_created", "copies_rule": "per_lot_quantity", "max_copies": 10},
    )
    assert resp.status_code == 200, resp.text
    stored = (await client.get(f"{BASE}/lot_label")).json()
    assert stored["trigger"] == "lot_created"
    assert stored["copies_rule"] == "per_lot_quantity"
