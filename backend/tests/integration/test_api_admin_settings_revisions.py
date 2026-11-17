"""
Wire-level round trip for the made-item revision rework's settings
additions. The unit tests (tests/unit/admin_settings/) exercise the
use cases directly with already-constructed Command objects, so they never
prove that a nested JSON body (revision_field_policy's list of objects,
the PDM variable maps) actually survives FastAPI/pydantic request parsing
and response serialisation. This file is that proof, over real HTTP
against a real (SQLite) DB, not a re-test of the validation rules
themselves; those are covered at the use-case level.

None of `admin_made_item_settings` / `admin_order_settings` /
`admin_pdm_settings` are seeded by conftest's autouse `_seed_admin_settings`
(only General/Storage/Maintenance/Banner are), so each test seeds what it
needs first, same pattern as test_api_banner_settings.py's
`_seed_remaining_settings_domains`.
"""

import pytest
from sqlalchemy.orm import Session

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.catalogue.domain.entities.admin_settings.made_items import AdminMadeItemSettings
from src.modules.catalogue.domain.entities.admin_settings.orders import AdminOrderSettings
from src.modules.catalogue.domain.policies.item_field_ownership import REVISION_POLICY_FIELDS
from src.modules.catalogue.domain.policies.item_field_ownership import default_policy
from src.modules.catalogue.domain.policies.item_field_ownership import item_fields
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.platform.domain.value_objects.permission import Permission

MADE_ITEMS_BASE = "/api/v1/web/admin/settings/made-items"
ORDERS_BASE = "/api/v1/web/admin/settings/orders"
PDM_BASE = "/api/v1/web/admin/settings/pdm"


@pytest.fixture(autouse=True)
async def _seed_settings(db: Session) -> None:
    repo = SqlAlchemyAdminSettingsRepository(db)
    await repo.save_orders(
        AdminOrderSettings(
            id=1,
            order_number_format="ORD-{yy}-{seq:05d}",
            part_number_format="PUR-{yy}-{seq:05d}",
            part_number_auto=True,
            part_number_editable=False,
            web_creation_allowed=True,
            pdm_part_number_pattern="",
        )
    )
    await db.commit()
    await repo.save_made_items(
        AdminMadeItemSettings(
            id=1,
            item_number_format="FAB-{yy}-{seq:05d}",
            lot_number_format="LOT-{yy}-{seq:05d}",
            part_number_auto=True,
            part_number_editable=False,
            revision_start="0",
            revision_separator=":",
            revision_skip_ambiguous_letters=False,
            revision_only_newest_editable=True,
            revision_predecessor_status_web="ask",
            revision_predecessor_status_pdm="replaced",
            revision_field_policy=default_policy(),
            web_creation_allowed=True,
            pdm_part_number_pattern="",
        )
    )
    await db.commit()
    await repo.save_pdm(
        AdminPdmSettings(
            id=1,
            made_item_variable_map={"part_number": "PDM.PartNumber", "revision": "PDM.Revision"},
            bought_item_variable_map={
                "part_number": "PDM.PartNumber",
                "revision": "PDM.Revision",
            },
            enabled=False,
            base_url="",
            vault_name="",
            username="",
            password=None,
            verify_certificate=True,
            timeout_seconds=15,
            watched_folders=[],
            made_released_state_ids=[],
            made_obsolete_state_ids=[],
            made_replaced_state_ids=[],
            bought_released_state_ids=[],
            bought_obsolete_state_ids=[],
            bought_replaced_state_ids=[],
            poll_interval_minutes=15,
            vault_id="",
            cad_items_read_only=True,
            last_poll_at=None,
            last_poll_error=None,
            last_poll_summary=None,
            writeback_enabled=False,
            session_token=None,
            session_user_id=None,
            session_obtained_at=None,
            made_item_extensions=["sldprt"],
            bought_item_extensions=["sldprt", "sldasm"],
            document_categories={"pdf": "drawing", "dxf": "dxf", "step": "step", "stp": "step"},
            thumbnails_enabled=False,
            stuck_after_days=7,
            reconcile_requested_deep=None,
            required_fields={"made": [], "bought": []},
        )
    )
    await db.commit()


@pytest.fixture
async def writer(auth_client):
    return await auth_client(permissions=[Permission.WRITE_SETTINGS, Permission.READ_SETTINGS])


class TestMadeItemRevisionSettingsRoundTrip:
    async def test_scalar_revision_fields_round_trip(self, writer):
        response = await writer.put(
            MADE_ITEMS_BASE,
            json={
                "revision_start": "A",
                "revision_separator": " rev ",
                "revision_skip_ambiguous_letters": True,
                "revision_only_newest_editable": False,
                "revision_predecessor_status_web": "inactive",
                "revision_predecessor_status_pdm": "active",
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["revision_start"] == "A"
        assert body["revision_separator"] == " rev "
        assert body["revision_skip_ambiguous_letters"] is True
        assert body["revision_only_newest_editable"] is False
        assert body["revision_predecessor_status_web"] == "inactive"
        assert body["revision_predecessor_status_pdm"] == "active"

        get_response = await writer.get(MADE_ITEMS_BASE)
        assert get_response.status_code == 200
        assert get_response.json()["revision_start"] == "A"

    async def test_revision_field_policy_list_round_trips(self, writer):
        toggled = [
            {
                "field": p.field,
                "web_requires_revision": not p.web_requires_revision,
                "pdm_update_in_place": p.pdm_update_in_place,
            }
            for p in default_policy()
        ]
        response = await writer.put(MADE_ITEMS_BASE, json={"revision_field_policy": toggled})
        assert response.status_code == 200, response.text

        by_field = {p["field"]: p for p in response.json()["revision_field_policy"]}
        assert set(by_field) == set(REVISION_POLICY_FIELDS)
        for original in default_policy():
            assert (
                by_field[original.field]["web_requires_revision"] != original.web_requires_revision
            )

        get_response = await writer.get(MADE_ITEMS_BASE)
        get_by_field = {p["field"]: p for p in get_response.json()["revision_field_policy"]}
        assert get_by_field == by_field

    async def test_pdm_part_number_pattern_round_trips(self, writer):
        response = await writer.put(MADE_ITEMS_BASE, json={"pdm_part_number_pattern": r"^EXT-\d+$"})
        assert response.status_code == 200, response.text
        assert response.json()["pdm_part_number_pattern"] == r"^EXT-\d+$"


class TestOrderSettingsRoundTrip:
    async def test_web_creation_and_pdm_pattern_round_trip(self, writer):
        response = await writer.put(
            ORDERS_BASE,
            json={"web_creation_allowed": False, "pdm_part_number_pattern": r"^EXT-\d+$"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["web_creation_allowed"] is False
        assert response.json()["pdm_part_number_pattern"] == r"^EXT-\d+$"


class TestPdmSettingsRoundTrip:
    async def test_variable_maps_round_trip(self, writer):
        fields = item_fields()
        identity = {"part_number": "PDM.PartNumber", "revision": "PDM.Revision"}
        made_map = {f.field: "" for f in fields["made"] if f.mappable} | identity
        made_map["article_name"] = "Glados.ArticleName"
        bought_map = {f.field: "" for f in fields["bought"] if f.mappable} | identity
        bought_map["gtin"] = "Glados.Gtin"
        response = await writer.put(
            PDM_BASE,
            json={"made_item_variable_map": made_map, "bought_item_variable_map": bought_map},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["made_item_variable_map"] == made_map
        assert body["bought_item_variable_map"] == bought_map

        get_response = await writer.get(PDM_BASE)
        assert get_response.status_code == 200
        assert get_response.json()["made_item_variable_map"] == made_map

    async def test_an_incomplete_variable_map_is_a_bad_request(self, writer):
        """A map that leaves out a mappable field is refused as invalid
        settings, not as a server error."""
        identity = {"part_number": "PDM.PartNumber", "revision": "PDM.Revision"}
        response = await writer.put(PDM_BASE, json={"made_item_variable_map": identity})
        assert response.status_code == 400, response.text
        assert "Missing made item field(s)" in response.text

    async def test_get_exposes_the_static_item_fields_table(self, writer):
        response = await writer.get(PDM_BASE)
        assert response.status_code == 200, response.text
        item_fields = response.json()["item_fields"]

        made_by_field = {f["field"]: f for f in item_fields["made"]}
        assert made_by_field["part_number"]["owner"] == "pdm"
        assert made_by_field["article_name"]["owner"] == "addin"
        assert made_by_field["article_name"]["mappable"] is True
        assert made_by_field["article_name"]["policy_applicable"] is True
        assert made_by_field["status"]["policy_applicable"] is False

        bought_by_field = {f["field"]: f for f in item_fields["bought"]}
        assert bought_by_field["gtin"]["owner"] == "addin"
        assert all(f["policy_applicable"] is False for f in item_fields["bought"])
