"""
HTTP-level coverage for GET /pat/settings/field-mapping (docs/reference/field-ownership.md
sections 2, 3 and 6): drives the real endpoint through the PAT auth chain (mint a real
token via CreatePat, same pattern as test_api_pat_surface.py) rather than
calling GetFieldMapping directly, so a broken deps-factory wiring, router
mount, or schema mismatch would fail these tests too, not just the unit
tests in tests/unit/admin_settings/.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from dataclasses import replace

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.platform.adapters.outbound.persistence.repositories.pat_repository import (
    SqlAlchemyPatRepository,
)
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.application.dto.pat_dto import CreatePatCommand
from src.modules.platform.application.use_cases.pat.create_pat import CreatePat
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission

_URL = "/api/v1/pat/settings/field-mapping"

_EXPECTED_MADE_FIELDS = [
    "part_number",
    "revision",
    "revision_date",
    "revision_note",
    "article_name",
    "material",
    "mass",
    "base_size",
    "note",
    "weblink",
    "article_group_ids",
    "bought_item_id",
    "source_item_id",
    "processes",
    "status",
    "successor_item_id",
    "approver_id",
    "files",
    "data_source",
    "kind",
    "glados_ids",
    "newest_revision_sync_state",
    "newest_revision_synced_at",
    "article_group_names",
    "process_names",
    "source_item_name",
    "feature_tree_representation",
    "customer_id",
    "customer_part_number",
    "customer_revision",
    "customer_name",
]

_EXPECTED_BOUGHT_FIELDS = [
    "part_number",
    "revision",
    "article_name",
    "order_code_1",
    "order_code_2",
    "gtin",
    "ean",
    "tariff_number",
    "mass",
    "note",
    "weblink",
    "manufacturer_id",
    "article_group_ids",
    "status",
    "successor_item_id",
    "approver_id",
    "files",
    "data_source",
    "kind",
    "glados_ids",
    "newest_revision_sync_state",
    "newest_revision_synced_at",
    "manufacturer_name",
    "article_group_names",
    "feature_tree_representation",
    "edp_part_id",
]


@pytest.fixture
async def pat_owner(create_user) -> User:
    return await create_user(
        username="pat-owner-fm",
        email="pat-owner-fm@example.com",
        permissions=[Permission.WRITE_PAT],
    )


@pytest.fixture
def mint_pat(db: AsyncSession, pat_owner: User) -> Callable[[list[str]], Awaitable[str]]:
    """Mints a real PAT via CreatePat, scoped to `permissions`, and returns
    the raw token (visible only at creation)."""

    async def _mint(permissions: list[str]) -> str:
        result = await CreatePat(
            SqlAlchemyPatRepository(db),
            settings_repo=SqlAlchemyAdminSettingsRepository(db),
            uow=SqlAlchemyUnitOfWork(db),
        ).execute(
            actor=pat_owner,
            cmd=CreatePatCommand(name="test-pat", permissions=permissions),
        )
        return result.token

    return _mint


async def test_missing_credential_is_rejected(client: httpx.AsyncClient) -> None:
    resp = await client.get(_URL)
    assert resp.status_code == 401


async def test_defaults_served_on_fresh_settings(
    client: httpx.AsyncClient, mint_pat: Callable[[list[str]], Awaitable[str]]
) -> None:
    """No permission beyond a valid PAT is required (an empty-scope token
    still gets 200), and a freshly-seeded install already reports the
    docs/FIELD_OWNERSHIP.md default custom-property names and revision
    policy; see get_field_mapping.py's docstring on why no per-request
    fallback is needed for that."""
    token = await mint_pat([])

    resp = await client.get(_URL, headers={"X-Api-Key": token})

    assert resp.status_code == 200
    body = resp.json()
    assert [e["field"] for e in body["made_items"]] == _EXPECTED_MADE_FIELDS
    assert [e["field"] for e in body["bought_items"]] == _EXPECTED_BOUGHT_FIELDS

    made = {e["field"]: e for e in body["made_items"]}
    bought = {e["field"]: e for e in body["bought_items"]}

    # Owner values (see item_field_ownership.item_fields()).
    assert made["part_number"]["owner"] == "pdm"
    assert made["article_name"]["owner"] == "addin"
    assert made["source_item_id"]["owner"] == "addin_web"
    # Lifecycle status feature: status is PDM-owned (driven by workflow
    # state), successor_item_id stays web-owned.
    assert made["status"]["owner"] == "pdm"
    assert made["successor_item_id"]["owner"] == "web"
    assert made["data_source"]["owner"] == "server"
    assert bought["gtin"]["owner"] == "addin"
    assert bought["part_number"]["owner"] == "pdm"
    assert made["kind"]["owner"] == "addin"
    assert bought["kind"]["owner"] == "addin"
    assert made["glados_ids"]["owner"] == "server"
    assert made["newest_revision_sync_state"]["owner"] == "server"
    assert made["newest_revision_synced_at"]["owner"] == "server"
    assert bought["glados_ids"]["owner"] == "server"
    assert bought["newest_revision_sync_state"]["owner"] == "server"
    assert bought["newest_revision_synced_at"]["owner"] == "server"
    assert bought["edp_part_id"]["owner"] == "addin_web"

    # Default custom-property names (docs/reference/field-ownership.md sections 2 and 3).
    assert made["part_number"]["custom_property"] == "PDM.PartNumber"
    assert made["article_name"]["custom_property"] == "Glados.ArticleName"
    assert made["source_item_id"]["custom_property"] == "Glados.SourceItemId"
    assert bought["order_code_1"]["custom_property"] == "Glados.OrderCode1"
    assert made["kind"]["custom_property"] == "Glados.Kind"
    assert bought["kind"]["custom_property"] == "Glados.Kind"
    assert made["glados_ids"]["custom_property"] == "Glados.Ids"
    assert made["newest_revision_sync_state"]["custom_property"] == "Glados.NewestRevisionSyncState"
    assert made["newest_revision_synced_at"]["custom_property"] == "Glados.NewestRevisionSyncedAt"
    assert bought["glados_ids"]["custom_property"] == "Glados.Ids"
    assert bought["edp_part_id"]["custom_property"] == "Glados.EdpPartId"
    assert made["revision_date"]["custom_property"] == "PDM.RevisionDate"
    assert made["revision_note"]["custom_property"] == "PDM.RevisionNote"
    # Web/server fields have no PDM counterpart.
    assert made["status"]["custom_property"] is None
    assert made["data_source"]["custom_property"] is None

    # update_in_place from the default revision policy.
    assert made["mass"]["update_in_place"] is True
    assert made["article_name"]["update_in_place"] is False
    assert made["part_number"]["update_in_place"] is None
    assert made["status"]["update_in_place"] is None
    assert made["kind"]["update_in_place"] is None
    assert made["glados_ids"]["update_in_place"] is None
    assert all(e["update_in_place"] is None for e in body["bought_items"])

    # Required-field validation (docs/reference/pdm-ingest.md section 7): locked
    # fields are always required, and the seeded default additionally
    # requires "material" for made items and, for bought items, keeps
    # revision required (it is not locked for them, see
    # test_required_field_selection_is_reflected for turning it off).
    assert made["part_number"]["required"] is True
    assert made["revision"]["required"] is True
    assert made["article_name"]["required"] is True
    assert made["material"]["required"] is True
    assert made["mass"]["required"] is False
    assert bought["order_code_1"]["required"] is True
    assert bought["manufacturer_id"]["required"] is True
    assert bought["revision"]["required"] is True
    assert bought["gtin"]["required"] is False

    assert body["rules"] == {
        "made": [{"name": "fabrication_step", "required": True}],
        "bought": [],
    }

    # Label fields and the feature-tree render field (docs/FIELD_OWNERSHIP.md
    # "Label properties and the feature-tree template" section): normal
    # mappable, addin-owned rows, `label_of` names the source field.
    assert made["article_group_names"]["owner"] == "addin"
    assert made["article_group_names"]["label_of"] == "article_group_ids"
    assert made["article_group_names"]["custom_property"] == "Glados.ArticleGroupNames"
    assert made["process_names"]["label_of"] == "processes"
    assert made["source_item_name"]["label_of"] == "source_item_id"
    assert made["feature_tree_representation"]["owner"] == "addin"
    assert made["feature_tree_representation"]["label_of"] is None
    assert made["article_name"]["label_of"] is None
    assert bought["manufacturer_name"]["owner"] == "addin"
    assert bought["manufacturer_name"]["label_of"] == "manufacturer_id"
    assert bought["manufacturer_name"]["custom_property"] == "Glados.ManufacturerName"
    assert bought["article_group_names"]["label_of"] == "article_group_ids"
    assert bought["feature_tree_representation"]["label_of"] is None

    # Feature-tree templates default (docs/FIELD_OWNERSHIP.md same section).
    assert body["templates"] == {
        "made": '$PRP:"PDM.PartNumber" Rev$PRP:"PDM.Revision" ($PRP:"Glados.ArticleName")',
        "bought": (
            '$PRP:"Glados.ArticleName" - $PRP:"Glados.OrderCode1" - $PRP:"Glados.ManufacturerName"'
        ),
    }


async def test_configured_variable_map_is_reflected(
    db: AsyncSession, client: httpx.AsyncClient, mint_pat: Callable[[list[str]], Awaitable[str]]
) -> None:
    repo = SqlAlchemyAdminSettingsRepository(db)
    current = await repo.get_pdm()
    made_map = dict(current.made_item_variable_map)
    made_map["material"] = "Glados.CustomMaterial"
    await repo.save_pdm(
        AdminPdmSettings(
            id=1,
            made_item_variable_map=made_map,
            bought_item_variable_map=current.bought_item_variable_map,
            enabled=current.enabled,
            base_url=current.base_url,
            vault_name=current.vault_name,
            username=current.username,
            password=current.password,
            verify_certificate=current.verify_certificate,
            timeout_seconds=current.timeout_seconds,
            session_token=current.session_token,
            session_user_id=current.session_user_id,
            session_obtained_at=current.session_obtained_at,
            watched_folders=current.watched_folders,
            made_released_state_ids=current.made_released_state_ids,
            made_obsolete_state_ids=current.made_obsolete_state_ids,
            made_replaced_state_ids=current.made_obsolete_state_ids,
            bought_released_state_ids=current.bought_released_state_ids,
            bought_obsolete_state_ids=current.bought_obsolete_state_ids,
            bought_replaced_state_ids=current.bought_obsolete_state_ids,
            poll_interval_minutes=current.poll_interval_minutes,
            vault_id=current.vault_id,
            cad_items_read_only=current.cad_items_read_only,
            last_poll_at=current.last_poll_at,
            last_poll_error=current.last_poll_error,
            last_poll_summary=current.last_poll_summary,
            writeback_enabled=current.writeback_enabled,
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
    token = await mint_pat([])

    resp = await client.get(_URL, headers={"X-Api-Key": token})

    made = {e["field"]: e for e in resp.json()["made_items"]}
    assert made["material"]["custom_property"] == "Glados.CustomMaterial"


async def test_unmapped_field_reports_null_custom_property(
    db: AsyncSession, client: httpx.AsyncClient, mint_pat: Callable[[list[str]], Awaitable[str]]
) -> None:
    """A field explicitly mapped to "" (UpdatePdmSettings' own "not mapped"
    sentinel) reports null, same as a field absent from the map entirely."""
    repo = SqlAlchemyAdminSettingsRepository(db)
    current = await repo.get_pdm()
    made_map = dict(current.made_item_variable_map)
    made_map["note"] = ""
    await repo.save_pdm(
        AdminPdmSettings(
            id=1,
            made_item_variable_map=made_map,
            bought_item_variable_map=current.bought_item_variable_map,
            enabled=current.enabled,
            base_url=current.base_url,
            vault_name=current.vault_name,
            username=current.username,
            password=current.password,
            verify_certificate=current.verify_certificate,
            timeout_seconds=current.timeout_seconds,
            session_token=current.session_token,
            session_user_id=current.session_user_id,
            session_obtained_at=current.session_obtained_at,
            watched_folders=current.watched_folders,
            made_released_state_ids=current.made_released_state_ids,
            made_obsolete_state_ids=current.made_obsolete_state_ids,
            made_replaced_state_ids=current.made_obsolete_state_ids,
            bought_released_state_ids=current.bought_released_state_ids,
            bought_obsolete_state_ids=current.bought_obsolete_state_ids,
            bought_replaced_state_ids=current.bought_obsolete_state_ids,
            poll_interval_minutes=current.poll_interval_minutes,
            vault_id=current.vault_id,
            cad_items_read_only=current.cad_items_read_only,
            last_poll_at=current.last_poll_at,
            last_poll_error=current.last_poll_error,
            last_poll_summary=current.last_poll_summary,
            writeback_enabled=current.writeback_enabled,
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
    token = await mint_pat([])

    resp = await client.get(_URL, headers={"X-Api-Key": token})

    made = {e["field"]: e for e in resp.json()["made_items"]}
    assert made["note"]["custom_property"] is None


async def test_label_fields_use_default_custom_property_names(
    client: httpx.AsyncClient, mint_pat: Callable[[list[str]], Awaitable[str]]
) -> None:
    token = await mint_pat([])

    resp = await client.get(_URL, headers={"X-Api-Key": token})

    assert resp.status_code == 200
    made = {e["field"]: e for e in resp.json()["made_items"]}
    bought = {e["field"]: e for e in resp.json()["bought_items"]}
    assert made["article_group_names"]["custom_property"] == "Glados.ArticleGroupNames"
    assert made["process_names"]["custom_property"] == "Glados.ProcessNames"
    assert made["source_item_name"]["custom_property"] == "Glados.SourceItemName"
    assert bought["manufacturer_name"]["custom_property"] == "Glados.ManufacturerName"
    assert bought["article_group_names"]["custom_property"] == "Glados.ArticleGroupNames"


async def test_label_field_custom_property_is_independent_of_its_source(
    db: AsyncSession, client: httpx.AsyncClient, mint_pat: Callable[[list[str]], Awaitable[str]]
) -> None:
    """A label's own custom property is stored and edited independently
    of its source field: unmapping the source field does not affect it."""
    repo = SqlAlchemyAdminSettingsRepository(db)
    current = await repo.get_pdm()
    made_map = dict(current.made_item_variable_map)
    made_map["processes"] = ""
    await repo.save_pdm(replace(current, made_item_variable_map=made_map))
    await db.commit()
    token = await mint_pat([])

    resp = await client.get(_URL, headers={"X-Api-Key": token})

    made = {e["field"]: e for e in resp.json()["made_items"]}
    assert made["processes"]["custom_property"] is None
    assert made["process_names"]["custom_property"] == "Glados.ProcessNames"


async def test_required_field_selection_is_reflected(
    db: AsyncSession, client: httpx.AsyncClient, mint_pat: Callable[[list[str]], Awaitable[str]]
) -> None:
    """An admin-configured selection (docs/reference/pdm-ingest.md section 7) shows
    up as `required: true` on that field and, for the pseudo-rule, on the
    matching `rules` entry. The locked fields stay required regardless."""
    repo = SqlAlchemyAdminSettingsRepository(db)
    current = await repo.get_pdm()
    await repo.save_pdm(replace(current, required_fields={"made": [], "bought": []}))
    await db.commit()
    token = await mint_pat([])

    resp = await client.get(_URL, headers={"X-Api-Key": token})

    made = {e["field"]: e for e in resp.json()["made_items"]}
    assert made["material"]["required"] is False
    assert made["part_number"]["required"] is True
    assert resp.json()["rules"] == {
        "made": [{"name": "fabrication_step", "required": False}],
        "bought": [],
    }


async def test_bought_revision_can_be_turned_off(
    db: AsyncSession, client: httpx.AsyncClient, mint_pat: Callable[[list[str]], Awaitable[str]]
) -> None:
    """Unlike part_number/article_name/order_code_1/manufacturer_id, a
    bought item's revision is not locked (docs/FIELD_OWNERSHIP.md
    principle 2), so deselecting it in required_fields turns it off."""
    repo = SqlAlchemyAdminSettingsRepository(db)
    current = await repo.get_pdm()
    await repo.save_pdm(replace(current, required_fields={"made": [], "bought": []}))
    await db.commit()
    token = await mint_pat([])

    resp = await client.get(_URL, headers={"X-Api-Key": token})

    bought = {e["field"]: e for e in resp.json()["bought_items"]}
    assert bought["revision"]["required"] is False
    assert bought["part_number"]["required"] is True
