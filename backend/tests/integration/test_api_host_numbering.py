"""
GET /host/numbering: the made-item revision rework's extension of the
numbering policy, adding a nested `revision` object on the made-items
policy (start, separator, skip_ambiguous_letters, only_newest_editable,
predecessor_status_web, field_policy) plus, on both kinds, the resolved
`web_creation_allowed` and `external_pattern`. Like
/host/capabilities, this endpoint is reachable by any authenticated user
(see host.py's own docstring); unlike /admin/settings/, no read:settings
is required. conftest's autouse `_seed_admin_settings` only seeds
General/Storage/Maintenance/Banner, so this file seeds made-items/orders
itself, same pattern as test_api_made_items.py's own fixture.
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

BASE = "/api/v1/web/host/numbering"


@pytest.fixture(autouse=True)
async def _seed_numbering_settings(db: Session) -> None:
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


class TestNumberingPolicyVisibleToAnyAuthenticatedUser:
    async def test_a_non_admin_user_can_read_the_policy(self, auth_client):
        client = await auth_client(permissions=[])

        response = await client.get(BASE)

        assert response.status_code == 200, response.text

    async def test_pdm_enforcement_flags_default_disabled_and_read_only(self, auth_client):
        # The autouse-seeded PDM row is disabled and unconfigured
        # (is_pdm_enabled() is False) but cad_items_read_only defaults to
        # the ORM column's server_default "true".
        client = await auth_client(permissions=[])

        response = await client.get(BASE)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["pdm_enabled"] is False
        assert body["cad_items_read_only"] is True

    async def test_pdm_enforcement_flags_reflect_saved_settings(self, auth_client, db):
        client = await auth_client(permissions=[])

        repo = SqlAlchemyAdminSettingsRepository(db)
        pdm = await repo.get_pdm()
        pdm.enabled = True
        pdm.base_url = "http://pdm-host:65453"
        pdm.vault_name = "MyVault"
        pdm.username = "svc-account"
        pdm.password = "secret"
        pdm.cad_items_read_only = False
        await repo.save_pdm(pdm)
        await db.commit()

        response = await client.get(BASE)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["pdm_enabled"] is True
        assert body["cad_items_read_only"] is False

    async def test_made_items_carry_the_revision_policy_with_seeded_defaults(self, auth_client):
        client = await auth_client(permissions=[])

        response = await client.get(BASE)

        assert response.status_code == 200, response.text
        made_items = response.json()["made_items"]
        revision = made_items["revision"]
        assert revision["start"] == "0"
        assert revision["separator"] == ":"
        assert revision["skip_ambiguous_letters"] is False
        assert revision["only_newest_editable"] is True
        assert revision["predecessor_status_web"] == "ask"

        by_field = {entry["field"]: entry for entry in revision["field_policy"]}
        assert set(by_field) == set(REVISION_POLICY_FIELDS)
        for entry in default_policy():
            assert by_field[entry.field]["web_requires_revision"] == entry.web_requires_revision
            # The wire shape is web-only: PDM's pdm_update_in_place is not
            # the web client's concern (see host.py's RevisionFieldPolicyEntry).
            assert "pdm_update_in_place" not in by_field[entry.field]

    async def test_web_creation_allowed_and_external_pattern_on_both_kinds(self, auth_client, db):
        client = await auth_client(permissions=[])

        response = await client.get(BASE)

        assert response.status_code == 200, response.text
        body = response.json()
        # Resolved as settings.web_creation_allowed OR NOT is_pdm_enabled():
        # the autouse-seeded PDM row is disabled and unconfigured, so
        # is_pdm_enabled() is False here and a seeded True stays True
        # regardless.
        assert body["made_items"]["web_creation_allowed"] is True
        assert body["bought_items"]["web_creation_allowed"] is True
        assert body["made_items"]["external_pattern"] == ""
        assert body["bought_items"]["external_pattern"] == ""

        repo = SqlAlchemyAdminSettingsRepository(db)
        made_items = await repo.get_made_items()
        made_items.web_creation_allowed = False
        made_items.pdm_part_number_pattern = r"^SW-\d+$"
        await repo.save_made_items(made_items)
        await db.commit()
        orders = await repo.get_orders()
        orders.pdm_part_number_pattern = r"^SW-\d+$"
        await repo.save_orders(orders)
        await db.commit()

        response = await client.get(BASE)
        body = response.json()
        # is_pdm_enabled() is still False here (the PDM row this test never
        # touches stays disabled and unconfigured), so web_creation_allowed
        # still resolves True even though the admin setting itself is
        # False (`... or not is_pdm_enabled()`).
        assert body["made_items"]["web_creation_allowed"] is True
        assert body["made_items"]["external_pattern"] == r"^SW-\d+$"
        assert body["bought_items"]["external_pattern"] == r"^SW-\d+$"
